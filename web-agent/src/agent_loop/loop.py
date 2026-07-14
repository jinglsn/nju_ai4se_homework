from dataclasses import dataclass, field
import asyncio
import json
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
                # 把 assistant 消息（含 tool_calls）追加到对话
                assistant_msg = {"role": "assistant", "content": response.text or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id or f"call_{i}",
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args, ensure_ascii=False)},
                    }
                    for i, tc in enumerate(response.tool_calls)
                ]
                messages.append(assistant_msg)

                for i, tc in enumerate(response.tool_calls):
                    intercept = classify_action(tc.name, tc.args)
                    decision = self.hitl.check(intercept)

                    if decision is None:
                        if not self._handle_hitl_intercept(intercept, tc):
                            logs.append(f"User denied: {tc.name}")
                            continue

                    result = self.tools.execute(tc.name, tc.args)
                    logs.append(f"Tool {tc.name}: {result.success}")

                    # 把工具结果追加到对话
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or f"call_{i}",
                        "content": result.output[:2000] if result.output else result.error or "",
                    })

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

    def _build_initial_messages(self, task: str, memory_context: str, selected_files: list[str] | None = None) -> list[dict]:
        # List workspace files for context
        workspace_files = []
        try:
            for p in self.workspace.rglob("*"):
                if p.is_file() and ".harness" not in p.parts and ".originals" not in p.parts:
                    workspace_files.append(str(p.relative_to(self.workspace)))
        except Exception:
            pass

        file_listing = "\n".join(f"  - {f}" for f in sorted(workspace_files)) if workspace_files else "  (empty)"

        system_prompt = (
            "You are a coding agent that fixes bugs in software projects. "
            "Follow this workflow:\n"
            "1. Explore the workspace: use list_dir '.' to see the project structure\n"
            "2. Read the relevant source files and test files to understand the code\n"
            "3. Run the tests with run_shell to see what's failing (e.g. 'python -m pytest tests/ -v')\n"
            "4. Analyze the test failures and identify the bugs in the source code\n"
            "5. Use edit_file to fix each bug — make precise, minimal changes\n"
            "6. Run the tests again to verify all tests pass\n"
            "7. If tests still fail, repeat from step 4\n\n"
            "IMPORTANT: Always use edit_file (search+replace) rather than write_file to modify existing files. "
            "The search string must match the code exactly, including whitespace. "
            "Fix one bug at a time, then re-run tests to verify before moving on."
        )
        if selected_files:
            system_prompt += (
                f"\n\n[Selected Files - ONLY modify these]\n"
                + "\n".join(f"  - {f}" for f in selected_files)
                + "\n\nCRITICAL: You MUST ONLY modify the files listed above. "
                "Do NOT edit any other files even if you find bugs in them."
            )
        if memory_context:
            system_prompt += f"\n\n[Project Context]\n{memory_context}"
        system_prompt += f"\n\nWorkspace: {self.workspace}\nFiles in workspace:\n{file_listing}"
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

    async def run_stream(self, task: str, selected_files: list[str] | None = None):
        """Async generator: yield events as agent runs for web streaming."""
        max_iterations = self.config.get("max_iterations", 10)
        judge = StopJudge(max_iterations=max_iterations)

        memory_context = self.memory_retriever.retrieve(task, max_chars=500)
        messages = self._build_initial_messages(task, memory_context, selected_files)
        previous_test_output = None
        iteration = 0

        while True:
            iteration += 1
            yield {"type": "iteration", "iteration": iteration}

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self.llm.chat, messages, self.tools.list_tools()
            )

            if response.error:
                yield {"type": "error", "message": response.error}
                return

            yield {"type": "llm_response", "text": response.text or "", "tool_calls": [
                {"name": tc.name, "args": tc.args, "id": tc.id}
                for tc in (response.tool_calls or [])
            ]}

            test_passed = False

            if response.tool_calls:
                assistant_msg = {"role": "assistant", "content": response.text or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id or f"call_{i}",
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args, ensure_ascii=False)},
                    }
                    for i, tc in enumerate(response.tool_calls)
                ]
                messages.append(assistant_msg)

                for i, tc in enumerate(response.tool_calls):
                    intercept = classify_action(tc.name, tc.args)
                    decision = self.hitl.check(intercept)

                    if decision is None:
                        if self.hitl.web_mode:
                            yield {
                                "type": "hitl_required",
                                "tool": tc.name,
                                "args": {k: str(v)[:200] for k, v in tc.args.items()},
                                "reason": intercept.reason,
                                "call_id": tc.id or f"call_{i}",
                            }
                            approved = await self.hitl.wait_for_decision()
                            if not approved:
                                yield {"type": "tool_denied", "tool": tc.name}
                                continue
                        else:
                            if not self._handle_hitl_intercept(intercept, tc):
                                yield {"type": "tool_denied", "tool": tc.name}
                                continue

                    yield {"type": "tool_start", "tool": tc.name, "args": {k: str(v)[:200] for k, v in tc.args.items()}}
                    result = await loop.run_in_executor(
                        None, self.tools.execute, tc.name, tc.args
                    )
                    yield {"type": "tool_result", "tool": tc.name, "success": result.success, "output": (result.output or result.error or "")[:2000]}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or f"call_{i}",
                        "content": result.output[:2000] if result.output else result.error or "",
                    })

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
                        yield {"type": "feedback", "test_result": feedback.test_result, "summary": feedback.summary}

            stop_reason = judge.should_stop(
                iteration=iteration,
                test_passed=test_passed,
                llm_text=response.text,
                tool_calls=response.tool_calls,
            )

            if stop_reason is not None:
                if stop_reason == StopReason.TEST_PASSED:
                    self.memory_store.add_fix_record({
                        "error_type": "resolved",
                        "task": task[:200],
                    })
                yield {"type": "stop", "reason": stop_reason.value, "success": stop_reason == StopReason.TEST_PASSED}
                return