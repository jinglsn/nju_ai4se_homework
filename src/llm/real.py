import json
import httpx
from src.llm.base import LLMBackend, LLMResponse, ToolCall
from src.config.keyring import get_api_key


class RealLLM(LLMBackend):
    def __init__(self, config: dict):
        llm_config = config.get("llm", {})
        self.model = llm_config.get("model", "glm-5.2")
        self.base_url = llm_config.get("base_url", "https://njusehub.info/v1")
        self.timeout = llm_config.get("timeout", 30)
        self.max_retries = llm_config.get("max_retries", 3)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        api_key = get_api_key()
        if not api_key:
            return LLMResponse(error="API key not configured. Run: harness keyring set")

        body = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]

        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                if response.status_code == 200:
                    data = response.json()
                    choice = data["choices"][0]["message"]
                    text = choice.get("content")
                    raw_tool_calls = choice.get("tool_calls")
                    tool_calls = None
                    if raw_tool_calls:
                        tool_calls = []
                        for tc in raw_tool_calls:
                            func = tc["function"]
                            try:
                                args = json.loads(func["arguments"])
                            except (json.JSONDecodeError, KeyError):
                                args = {}
                            tool_calls.append(ToolCall(name=func["name"], args=args))
                    return LLMResponse(text=text, tool_calls=tool_calls)
                else:
                    return LLMResponse(error=f"API error {response.status_code}: {response.text[:500]}")
            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    continue
                return LLMResponse(error="Request timeout after retries")
            except Exception as e:
                if attempt < self.max_retries - 1:
                    continue
                return LLMResponse(error=str(e))
        return LLMResponse(error="Max retries exceeded")