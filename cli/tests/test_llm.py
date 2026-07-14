import pytest
from src.llm.base import LLMResponse, ToolCall, LLMBackend
from src.llm.mock import MockLLM


class TestLLMBase:
    def test_llm_response_defaults(self):
        resp = LLMResponse()
        assert resp.text is None
        assert resp.tool_calls is None
        assert resp.error is None

    def test_llm_response_with_text(self):
        resp = LLMResponse(text="hello")
        assert resp.text == "hello"
        assert resp.tool_calls is None

    def test_llm_response_with_error(self):
        resp = LLMResponse(error="timeout")
        assert resp.error == "timeout"
        assert resp.text is None

    def test_tool_call_creation(self):
        tc = ToolCall(name="read_file", args={"path": "test.py"})
        assert tc.name == "read_file"
        assert tc.args == {"path": "test.py"}

    def test_llm_backend_is_abstract(self):
        with pytest.raises(TypeError):
            LLMBackend()

    def test_llm_backend_subclass_must_implement_chat(self):
        class Incomplete(LLMBackend):
            pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_backend_works(self):
        class Simple(LLMBackend):
            def chat(self, messages, tools=None):
                return LLMResponse(text="ok")
        backend = Simple()
        result = backend.chat([{"role": "user", "content": "hi"}])
        assert result.text == "ok"


class TestMockLLM:
    def test_returns_preset_responses(self):
        mock = MockLLM(responses=[
            LLMResponse(tool_calls=[ToolCall(name="read_file", args={"path": "x.py"})]),
            LLMResponse(text="done"),
        ])
        r1 = mock.chat([{"role": "user", "content": "task"}])
        assert len(r1.tool_calls) == 1
        assert r1.tool_calls[0].name == "read_file"
        r2 = mock.chat([{"role": "user", "content": "continue"}])
        assert r2.text == "done"

    def test_call_count(self):
        mock = MockLLM(responses=[LLMResponse(text="a"), LLMResponse(text="b")])
        assert mock.call_count == 0
        mock.chat([{"role": "user", "content": "q"}])
        assert mock.call_count == 1
        mock.chat([{"role": "user", "content": "q"}])
        assert mock.call_count == 2

    def test_call_history(self):
        mock = MockLLM(responses=[LLMResponse(text="ok")])
        mock.chat([{"role": "user", "content": "hello"}], tools=[{"name": "grep"}])
        assert len(mock.call_history) == 1
        assert mock.call_history[0]["messages"][0]["content"] == "hello"
        assert mock.call_history[0]["tools"][0]["name"] == "grep"

    def test_error_response(self):
        mock = MockLLM(responses=[LLMResponse(error="timeout")])
        r = mock.chat([{"role": "user", "content": "q"}])
        assert r.error == "timeout"
        assert r.text is None

    def test_exhausted_raises(self):
        mock = MockLLM(responses=[LLMResponse(text="only one")])
        mock.chat([{"role": "user", "content": "q"}])
        with pytest.raises(IndexError):
            mock.chat([{"role": "user", "content": "q2"}])