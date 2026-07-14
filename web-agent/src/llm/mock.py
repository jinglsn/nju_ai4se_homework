from src.llm.base import LLMBackend, LLMResponse


class MockLLM(LLMBackend):
    def __init__(self, responses: list[LLMResponse] | None = None):
        self._responses = responses or []
        self._index = 0
        self.call_history: list[dict] = []

    @property
    def call_count(self) -> int:
        return len(self.call_history)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        self.call_history.append({
            "messages": [dict(m) for m in messages],
            "tools": [dict(t) for t in tools] if tools else None,
        })
        if self._index >= len(self._responses):
            raise IndexError(f"MockLLM exhausted: only {len(self._responses)} responses preset")
        response = self._responses[self._index]
        self._index += 1
        return response