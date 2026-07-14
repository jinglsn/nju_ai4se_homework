from dataclasses import dataclass, field
from pathlib import Path
from src.llm.base import LLMBackend
from src.tools.registry import ToolRegistry
from src.guardrail.classifier import classify_action
from src.guardrail.hitl import HITLStateMachine, HITLDecision
from src.feedback.builder import build_feedback
from src.memory.store import MemoryStore
from src.memory.retriever import MemoryRetriever
from src.agent_loop.stop_judge import StopJudge, StopReason


@dataclass
class LoopResult:
    success: bool
    stop_reason: str
    iterations: int
    logs: list[str] = field(default_factory=list)


class AgentLoop:
    def __init__(self, llm: LLMBackend, tools: ToolRegistry, workspace: Path, config: dict):
        self.llm = llm
        self.tools = tools
        self.workspace = workspace
        self.config = config
        self.hitl = HITLStateMachine()
        self.harness_dir = workspace / ".harness"
        self.memory_store = MemoryStore(self.harness_dir)
        self.memory_retriever = MemoryRetriever(self.memory_store)

    def run(self, task: str) -> LoopResult:
        max_iterations = self.config.get("max_iterations", 10)
        judge = StopJudge(max_iterations=max_iterations)
        logs = []

        memory_context = self.memory_retriever.retrieve(task, max_chars=500)
        messages = self._build_initial_messages(task, memory_context)

        previous_test_output = None
        iteration = 0

        while True:
            iteration += 1
            logs.append(f"[Iteration {iteration}]")

            response = self.llm.chat(messages, self.tools.list_tools())
            if response.error:
                logs.append(f"LLM error: {response.error}")
                return LoopResult(
                    success=False,
                    stop_reason="llm_error",
                    iterations=iteration,
                    logs=logs,
                )

            test_passed = False

            if response.tool_calls:
                for tc in response.tool_calls:
                    intercept = classify_action(tc.name, tc.args)
                    decision = self.hitl.check(intercept)

                    if decision is None:
                        if not self._handle_hitl_intercept(intercept, tc):
                            logs.append(f"User denied: {tc.name}")
                            continue

                    result = self.tools.execute(tc.name, tc.args)
                    logs.append(f"Tool {tc.name}: {result.success}")

                    self.memory_store.add_audit_entry({
                        "action": "tool_exec",
                        "tool": tc.name,
                        "args": {k: str(v)[:200] for k, v in tc.args.items()},
                        "success": result.success,
                    })

                    if tc.name == "run_shell" and "pytest" in str(tc.args.get("command", "")):
                        feedback = build_feedback(result.output, previous_test_output)
                        previous_test_output = result.output
                        if feedback.test_result == "PASS":
                            test_passed = True
                        self._append_feedback(messages, feedback)

            stop_reason = judge.should_stop(
                iteration=iteration,
                test_passed=test_passed,
                llm_text=response.text,
                tool_calls=response.tool_calls,
            )

            if stop_reason is not None:
                logs.append(f"Stop: {stop_reason.value}")
                if stop_reason == StopReason.TEST_PASSED:
                    self.memory_store.add_fix_record({
                        "error_type": "resolved",
                        "task": task[:200],
                    })
                return LoopResult(
                    success=stop_reason == StopReason.TEST_PASSED,
                    stop_reason=stop_reason.value,
                    iterations=iteration,
                    logs=logs,
                )

    def _build_initial_messages(self, task: str, memory_context: str) -> list[dict]:
        system_prompt = "You are a coding agent. Your goal is to fix failing tests."
        if memory_context:
            system_prompt += f"\n\n[Project Context]\n{memory_context}"
        system_prompt += f"\nWorkspace: {self.workspace}"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

    def _handle_hitl_intercept(self, intercept, tool_call) -> bool:
        decision = self.hitl.request_approval(intercept)
        if decision == HITLDecision.ALWAYS:
            self.hitl.graylist.add(tool_call.name)
            self.memory_store.add_audit_entry({
                "action": "graylist_add",
                "tool": tool_call.name,
            })
        return decision in (HITLDecision.ALLOW, HITLDecision.ALWAYS)

    def _append_feedback(self, messages: list[dict], feedback) -> None:
        feedback_text = f"Test result: {feedback.test_result}\n{feedback.summary}"
        if feedback.regression:
            feedback_text += "\nWARNING: Regression detected!"
        for f in feedback.failures:
            feedback_text += f"\n- {f.type} @ {f.file}:{f.line}: {f.strategy}"
        messages.append({"role": "system", "content": feedback_text})