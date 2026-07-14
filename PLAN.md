# Coding Agent Harness 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个面向"测试驱动修复"场景的 Coding Agent Harness，CLI 交互 + Web 仪表盘，Docker 分发。

**Architecture:** 分层架构——底层 LLM 抽象 + 工具层，中层护栏 + 反馈闭环 + 记忆，上层 agent 主循环 + CLI 入口 + Web 仪表盘。所有核心机制用 mock LLM 做确定性单元测试。

**Tech Stack:** Python 3.13, pytest, FastAPI, keyring, Docker, GitHub Actions, Render

## Global Constraints

- Python >= 3.13
- 所有核心机制必须能用 mock/stub LLM 做确定性单元测试，不依赖网络与真实 LLM
- TDD 硬性要求：先写失败测试（红色），再写最小实现（绿色），再重构
- 机制必须是代码，不能是提示词
- 不允许依赖 LangChain AgentExecutor、AutoGen、CrewAI 等框架
- 凭据绝不硬编码、不提交 Git、不写入日志
- 仅需依赖：pytest, fastapi, uvicorn, keyring, httpx（测试用）

## 依赖关系图

```
Phase 1: Foundation (可并行)
  Task 1: 项目脚手架
  ├─ Task 2: LLM 抽象基类 + 数据模型
  ├─ Task 3: MockLLM 实现
  └─ Task 3.5: RealLLM 实现 (依赖 Task 2, Task 5)

Phase 2: 基础组件 (可并行)
  ├─ Task 4: 配置加载器
  ├─ Task 5: 凭据管理 (keyring)
  ├─ Task 6: 记忆存储 + 敏感信息过滤
  └─ Task 7: 记忆检索器

Phase 3: 工具层 (依赖 Task 1, Task 4)
  ├─ Task 8: 工具注册表 + 基础接口
  ├─ Task 9: 文件操作工具 (read/write/edit)
  └─ Task 10: 搜索与执行工具 (grep/list_dir/run_shell)

Phase 4: 护栏 + 反馈 (依赖 Task 1)
  ├─ Task 11: 护栏分级 + 沙箱校验
  ├─ Task 12: HITL 状态机
  ├─ Task 13: 反馈解析器 + 失败分类器
  └─ Task 14: 反馈构建器

Phase 5: 集成 (依赖 Phase 2-4)
  ├─ Task 15: Agent 主循环 + 停机判断
  ├─ Task 16: CLI 入口
  └─ Task 17: Web 仪表盘

Phase 6: 交付 (依赖 Phase 5)
  ├─ Task 18: Docker + CI/CD
  └─ Task 19: 机制演示脚本
```

---

### Task 1: 项目脚手架与依赖

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/llm/__init__.py`
- Create: `src/tools/__init__.py`
- Create: `src/guardrail/__init__.py`
- Create: `src/feedback/__init__.py`
- Create: `src/memory/__init__.py`
- Create: `src/config/__init__.py`
- Create: `src/agent_loop/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: nothing
- Produces: directory structure, `requirements.txt`, `conftest.py` with tmp_path fixture

- [ ] **Step 1: 创建 requirements.txt**

```txt
pytest>=8.0
fastapi>=0.115
uvicorn>=0.30
keyring>=25.0
```

- [ ] **Step 2: 创建所有 `__init__.py` 文件（空文件）**

```bash
mkdir -p src/llm src/tools src/guardrail src/feedback src/memory src/config src/agent_loop web tests
touch src/__init__.py
touch src/llm/__init__.py
touch src/tools/__init__.py
touch src/guardrail/__init__.py
touch src/feedback/__init__.py
touch src/memory/__init__.py
touch src/config/__init__.py
touch src/agent_loop/__init__.py
touch tests/__init__.py
```

- [ ] **Step 3: 创建 tests/conftest.py**

```python
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_workspace():
    """创建临时工作目录，模拟项目根目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "src").mkdir()
        (workspace / "tests").mkdir()
        yield workspace


@pytest.fixture
def temp_harness_dir():
    """创建临时 .harness 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        harness_dir = Path(tmpdir) / ".harness"
        harness_dir.mkdir()
        yield harness_dir
```

- [ ] **Step 4: 安装依赖并验证**

```bash
pip install -r requirements.txt
python -c "import pytest; import fastapi; import keyring; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/ tests/ web/
git commit -m "feat: project scaffolding and dependencies"
```

---

### Task 2: LLM 抽象基类 + 数据模型

**Files:**
- Create: `src/llm/base.py`
- Create: `tests/test_llm.py`

**Interfaces:**
- Consumes: Task 1 (directory structure)
- Produces: `LLMResponse`, `ToolCall` dataclasses, `LLMBackend` ABC with `chat(messages, tools) -> LLMResponse`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_llm.py
import pytest
from src.llm.base import LLMResponse, ToolCall, LLMBackend


def test_llm_response_defaults():
    resp = LLMResponse()
    assert resp.text is None
    assert resp.tool_calls is None
    assert resp.error is None


def test_llm_response_with_text():
    resp = LLMResponse(text="hello")
    assert resp.text == "hello"
    assert resp.tool_calls is None


def test_llm_response_with_error():
    resp = LLMResponse(error="timeout")
    assert resp.error == "timeout"
    assert resp.text is None


def test_tool_call_creation():
    tc = ToolCall(name="read_file", args={"path": "test.py"})
    assert tc.name == "read_file"
    assert tc.args == {"path": "test.py"}


def test_llm_backend_is_abstract():
    with pytest.raises(TypeError):
        LLMBackend()


def test_llm_backend_subclass_must_implement_chat():
    class Incomplete(LLMBackend):
        pass
    with pytest.raises(TypeError):
        Incomplete()


def test_concrete_backend_works():
    class Simple(LLMBackend):
        def chat(self, messages, tools=None):
            return LLMResponse(text="ok")

    backend = Simple()
    result = backend.chat([{"role": "user", "content": "hi"}])
    assert result.text == "ok"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_llm.py -v
# Expected: all FAIL (module not found)
```

- [ ] **Step 3: 实现 src/llm/base.py**

```python
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCall] | None = None
    error: str | None = None


class LLMBackend(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        ...
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_llm.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/llm/base.py tests/test_llm.py
git commit -m "feat: LLM abstract base class with data models"
```

---

### Task 3: MockLLM 实现

**Files:**
- Create: `src/llm/mock.py`
- Modify: `tests/test_llm.py` (追加测试)

**Interfaces:**
- Consumes: Task 2 (`LLMBackend`, `LLMResponse`, `ToolCall`)
- Produces: `MockLLM` with preset response queue, `call_history` tracking, `call_count` property

- [ ] **Step 1: 编写失败测试**

```python
# 追加到 tests/test_llm.py

from src.llm.mock import MockLLM


def test_mock_llm_returns_preset_responses():
    mock = MockLLM(responses=[
        LLMResponse(tool_calls=[ToolCall(name="read_file", args={"path": "x.py"})]),
        LLMResponse(text="done"),
    ])
    r1 = mock.chat([{"role": "user", "content": "task"}])
    assert len(r1.tool_calls) == 1
    assert r1.tool_calls[0].name == "read_file"

    r2 = mock.chat([{"role": "user", "content": "continue"}])
    assert r2.text == "done"


def test_mock_llm_call_count():
    mock = MockLLM(responses=[LLMResponse(text="a"), LLMResponse(text="b")])
    assert mock.call_count == 0
    mock.chat([{"role": "user", "content": "q"}])
    assert mock.call_count == 1
    mock.chat([{"role": "user", "content": "q"}])
    assert mock.call_count == 2


def test_mock_llm_call_history():
    mock = MockLLM(responses=[LLMResponse(text="ok")])
    mock.chat([{"role": "user", "content": "hello"}], tools=[{"name": "grep"}])
    assert len(mock.call_history) == 1
    assert mock.call_history[0]["messages"][0]["content"] == "hello"
    assert mock.call_history[0]["tools"][0]["name"] == "grep"


def test_mock_llm_error_response():
    mock = MockLLM(responses=[LLMResponse(error="timeout")])
    r = mock.chat([{"role": "user", "content": "q"}])
    assert r.error == "timeout"
    assert r.text is None


def test_mock_llm_exhausted_raises():
    mock = MockLLM(responses=[LLMResponse(text="only one")])
    mock.chat([{"role": "user", "content": "q"}])
    with pytest.raises(IndexError):
        mock.chat([{"role": "user", "content": "q2"}])
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_llm.py::test_mock_llm_returns_preset_responses -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/llm/mock.py**

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_llm.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/llm/mock.py tests/test_llm.py
git commit -m "feat: MockLLM with preset response queue and call history"
```

---

### Task 3.5: RealLLM 实现 (OpenAI 兼容 API)

**Files:**
- Create: `src/llm/real.py`
- Modify: `tests/test_llm.py` (追加测试)
- Modify: `requirements.txt` (添加 httpx)

**Interfaces:**
- Consumes: Task 2 (`LLMBackend`, `LLMResponse`, `ToolCall`), Task 5 (`get_api_key`)
- Produces: `RealLLM` class — 封装 njusehub.info OpenAI 兼容 API

**API 配置:**
- Base URL: `https://njusehub.info/v1`
- Auth: API Key from keyring
- Model: `glm-5.2`（默认，可在 config 中覆盖）

- [ ] **Step 1: 更新 requirements.txt 添加 httpx**

```txt
pytest>=8.0
fastapi>=0.115
uvicorn>=0.30
keyring>=25.0
httpx>=0.27
```

- [ ] **Step 2: 编写失败测试**

```python
# 追加到 tests/test_llm.py

from unittest.mock import patch, MagicMock
from src.llm.real import RealLLM


def test_real_llm_builds_openai_messages():
    llm = RealLLM(config={"llm": {"model": "glm-5.2", "base_url": "https://test.invalid"}})
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"name": "grep", "parameters": {"pattern": "str"}}]

    with patch("src.llm.real.get_api_key", return_value="test-key"):
        with patch("src.llm.real.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "hi there", "tool_calls": None}}]
            }
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = llm.chat(messages, tools)

    assert result.text == "hi there"
    assert result.tool_calls is None


def test_real_llm_handles_tool_calls():
    llm = RealLLM(config={"llm": {"model": "glm-5.2", "base_url": "https://test.invalid"}})
    messages = [{"role": "user", "content": "find tests"}]

    with patch("src.llm.real.get_api_key", return_value="test-key"):
        with patch("src.llm.real.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": None,
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "grep", "arguments": '{"pattern": "def test"}'}
                        }]
                    }
                }]
            }
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = llm.chat(messages)

    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "grep"
    assert result.tool_calls[0].args == {"pattern": "def test"}


def test_real_llm_handles_api_error():
    llm = RealLLM(config={"llm": {"model": "glm-5.2", "base_url": "https://test.invalid"}})

    with patch("src.llm.real.get_api_key", return_value="test-key"):
        with patch("src.llm.real.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = llm.chat([{"role": "user", "content": "hi"}])

    assert result.error is not None
    assert "500" in result.error


def test_real_llm_handles_timeout():
    llm = RealLLM(config={"llm": {"model": "glm-5.2", "base_url": "https://test.invalid"}})

    with patch("src.llm.real.get_api_key", return_value="test-key"):
        with patch("src.llm.real.httpx.Client") as mock_client:
            import httpx
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")

            result = llm.chat([{"role": "user", "content": "hi"}])

    assert result.error is not None
    assert "timeout" in result.error.lower()
```

- [ ] **Step 3: 验证测试失败**

```bash
python -m pytest tests/test_llm.py::test_real_llm_builds_openai_messages -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 4: 实现 src/llm/real.py**

```python
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

        body = {
            "model": self.model,
            "messages": messages,
        }
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
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_llm.py -v
# Expected: all PASS (RealLLM 测试使用 mock HTTP，不依赖网络)
```

- [ ] **Step 6: Commit**

```bash
git add src/llm/real.py tests/test_llm.py requirements.txt
git commit -m "feat: RealLLM for njusehub.info OpenAI-compatible API"
```

---

### Task 4: 配置加载器

**Files:**
- Create: `src/config/loader.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: Task 1 (directory structure)
- Produces: `load_config(project_root: Path) -> dict` — 合并全局+项目配置，`DEFAULT_CONFIG` 常量

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_config.py
import json
import pytest
from pathlib import Path
from src.config.loader import load_config, DEFAULT_CONFIG, merge_configs


def test_default_config_has_required_keys():
    assert "max_iterations" in DEFAULT_CONFIG
    assert "timeout" in DEFAULT_CONFIG
    assert "sandbox_root" in DEFAULT_CONFIG
    assert "max_file_change_ratio" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["max_iterations"] == 10
    assert DEFAULT_CONFIG["timeout"] == 120


def test_merge_configs_project_overrides_global():
    global_cfg = {"max_iterations": 10, "timeout": 120}
    project_cfg = {"max_iterations": 5}
    merged = merge_configs(global_cfg, project_cfg)
    assert merged["max_iterations"] == 5
    assert merged["timeout"] == 120


def test_merge_configs_nested_dict():
    global_cfg = {"tools": {"read_file": True, "run_shell": True}}
    project_cfg = {"tools": {"run_shell": False}}
    merged = merge_configs(global_cfg, project_cfg)
    assert merged["tools"]["read_file"] is True
    assert merged["tools"]["run_shell"] is False


def test_load_config_without_project_file(temp_harness_dir):
    project_root = temp_harness_dir.parent
    config = load_config(project_root)
    assert config["max_iterations"] == 10


def test_load_config_with_project_file(temp_harness_dir):
    project_root = temp_harness_dir.parent
    project_config = {"max_iterations": 3, "timeout": 60}
    with open(temp_harness_dir / "config.json", "w") as f:
        json.dump(project_config, f)

    config = load_config(project_root, global_config_path=None)
    assert config["max_iterations"] == 3
    assert config["timeout"] == 60
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_config.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/config/loader.py**

```python
import json
from pathlib import Path
from copy import deepcopy

DEFAULT_CONFIG = {
    "max_iterations": 10,
    "timeout": 120,
    "sandbox_root": None,
    "max_file_change_ratio": 0.3,
    "tools": {
        "read_file": True,
        "write_file": True,
        "edit_file": True,
        "grep": True,
        "list_dir": True,
        "run_shell": True,
    },
    "guardrail": {
        "level3_requires_confirm": True,
        "file_write_warn_threshold": 0.3,
    },
    "memory": {
        "enabled": True,
        "auto_write_on_success": True,
        "max_context_ratio": 0.15,
    },
    "test_command": "python -m pytest -v",
    "lint_command": None,
    "dir_depth_limit": 3,
}


def merge_configs(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def load_config(project_root: Path, global_config_path: Path | None = None) -> dict:
    config = deepcopy(DEFAULT_CONFIG)
    config["sandbox_root"] = str(project_root.resolve())

    if global_config_path is None:
        global_config_path = Path.home() / ".harness" / "global.json"
    if global_config_path.exists():
        with open(global_config_path) as f:
            global_cfg = json.load(f)
        config = merge_configs(config, global_cfg)

    project_config_path = project_root / ".harness" / "config.json"
    if project_config_path.exists():
        with open(project_config_path) as f:
            project_cfg = json.load(f)
        config = merge_configs(config, project_cfg)

    return config
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_config.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/config/loader.py tests/test_config.py
git commit -m "feat: config loader with global+project merge"
```

---

### Task 5: 凭据管理 (keyring)

**Files:**
- Create: `src/config/keyring.py`
- Create: `tests/test_keyring.py`

**Interfaces:**
- Consumes: Task 1 (directory structure)
- Produces: `set_api_key(service, key)`, `get_api_key(service) -> str | None`, `clear_api_key(service)`, `key_status(service) -> str`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_keyring.py
import pytest
from unittest.mock import patch, MagicMock
from src.config.keyring import set_api_key, get_api_key, clear_api_key, key_status

SERVICE_NAME = "harness-test"


@patch("src.config.keyring.keyring")
def test_set_and_get_api_key(mock_keyring):
    mock_keyring.get_password.return_value = "test-key-123"
    set_api_key(SERVICE_NAME, "test-key-123")
    mock_keyring.set_password.assert_called_once()
    assert get_api_key(SERVICE_NAME) == "test-key-123"


@patch("src.config.keyring.keyring")
def test_key_status_configured(mock_keyring):
    mock_keyring.get_password.return_value = "some-key"
    status = key_status(SERVICE_NAME)
    assert status == "configured"


@patch("src.config.keyring.keyring")
def test_key_status_not_configured(mock_keyring):
    mock_keyring.get_password.return_value = None
    status = key_status(SERVICE_NAME)
    assert status == "not configured"


@patch("src.config.keyring.keyring")
def test_clear_api_key(mock_keyring):
    clear_api_key(SERVICE_NAME)
    mock_keyring.delete_password.assert_called_once()


@patch("src.config.keyring.keyring")
def test_get_api_key_returns_none_when_missing(mock_keyring):
    mock_keyring.get_password.return_value = None
    assert get_api_key(SERVICE_NAME) is None
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_keyring.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/config/keyring.py**

```python
import keyring

DEFAULT_SERVICE = "harness-llm"


def set_api_key(service: str = DEFAULT_SERVICE, key: str | None = None) -> None:
    if key is None:
        import getpass
        key = getpass.getpass("Enter API key: ")
    keyring.set_password(service, "api_key", key)


def get_api_key(service: str = DEFAULT_SERVICE) -> str | None:
    return keyring.get_password(service, "api_key")


def clear_api_key(service: str = DEFAULT_SERVICE) -> None:
    try:
        keyring.delete_password(service, "api_key")
    except keyring.errors.PasswordDeleteError:
        pass


def key_status(service: str = DEFAULT_SERVICE) -> str:
    key = get_api_key(service)
    return "configured" if key else "not configured"
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_keyring.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/config/keyring.py tests/test_keyring.py
git commit -m "feat: credential management via system keyring"
```

---

### Task 6: 记忆存储 + 敏感信息过滤

**Files:**
- Create: `src/memory/store.py`
- Create: `tests/test_memory.py`

**Interfaces:**
- Consumes: Task 1 (directory structure)
- Produces: `MemoryStore` class with `load()`, `save(data)`, `add_fix_record(record)`, `add_audit_entry(entry)`, `clear()`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_memory.py
import json
import pytest
from pathlib import Path
from src.memory.store import MemoryStore
from src.memory.filter import filter_sensitive


def test_memory_store_creates_file(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    assert not store.memory_file.exists()
    data = store.load()
    assert data == {}


def test_memory_store_save_and_load(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.save({
        "project": {"name": "test"},
        "conventions": {"test_command": "pytest"},
        "fix_history": [],
        "graylist_commands": [],
        "audit_log": [],
    })
    assert store.memory_file.exists()
    loaded = store.load()
    assert loaded["project"]["name"] == "test"


def test_memory_store_add_fix_record(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.add_fix_record({
        "error_type": "AssertionError",
        "file": "calc.py",
        "strategy": "修复返回值",
    })
    data = store.load()
    assert len(data["fix_history"]) == 1
    assert data["fix_history"][0]["error_type"] == "AssertionError"


def test_memory_store_add_audit_entry(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.add_audit_entry({"action": "tool_exec", "tool": "run_shell", "command": "pytest"})
    data = store.load()
    assert len(data["audit_log"]) == 1
    assert data["audit_log"][0]["tool"] == "run_shell"


def test_memory_store_clear(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.save({"project": {"name": "test"}})
    store.clear()
    assert not store.memory_file.exists()


def test_filter_sensitive_removes_api_key():
    text = "my API key is sk-abc123def456"
    filtered = filter_sensitive(text)
    assert "sk-abc123def456" not in filtered


def test_filter_sensitive_removes_password():
    text = 'password: "secret123"'
    filtered = filter_sensitive(text)
    assert "secret123" not in filtered


def test_filter_sensitive_removes_token():
    text = "token=ghp_1234567890abcdef"
    filtered = filter_sensitive(text)
    assert "ghp_1234567890abcdef" not in filtered


def test_filter_sensitive_preserves_normal_text():
    text = "this is normal test output"
    assert filter_sensitive(text) == text
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_memory.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/memory/filter.py**

```python
import re

SENSITIVE_PATTERNS = [
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), '[API_KEY_REDACTED]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{20,}'), '[TOKEN_REDACTED]'),
    (re.compile(r'token[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}["\']?', re.IGNORECASE), 'token=[REDACTED]'),
    (re.compile(r'password[=:]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE), 'password=[REDACTED]'),
    (re.compile(r'secret[=:]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE), 'secret=[REDACTED]'),
    (re.compile(r'Authorization[=:]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE), 'Authorization=[REDACTED]'),
]


def filter_sensitive(text: str) -> str:
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
```

- [ ] **Step 4: 实现 src/memory/store.py**

```python
import json
from pathlib import Path
from datetime import datetime, timezone
from src.memory.filter import filter_sensitive


class MemoryStore:
    def __init__(self, harness_dir: Path):
        self.harness_dir = Path(harness_dir)
        self.memory_file = self.harness_dir / "project_memory.json"

    def _default_data(self) -> dict:
        return {
            "project": {},
            "conventions": {},
            "fix_history": [],
            "graylist_commands": [],
            "audit_log": [],
        }

    def load(self) -> dict:
        if not self.memory_file.exists():
            return self._default_data()
        with open(self.memory_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in self._default_data():
            if key not in data:
                data[key] = self._default_data()[key]
        return data

    def save(self, data: dict) -> None:
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        data_str = filter_sensitive(data_str)
        self.harness_dir.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            f.write(data_str)

    def add_fix_record(self, record: dict) -> None:
        data = self.load()
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        data["fix_history"].append(record)
        self.save(data)

    def add_audit_entry(self, entry: dict) -> None:
        data = self.load()
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        data["audit_log"].append(entry)
        self.save(data)

    def clear(self) -> None:
        if self.memory_file.exists():
            self.memory_file.unlink()
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_memory.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/memory/filter.py src/memory/store.py tests/test_memory.py
git commit -m "feat: memory store with sensitive info filtering"
```

---

### Task 7: 记忆检索器

**Files:**
- Create: `src/memory/retriever.py`
- Modify: `tests/test_memory.py` (追加测试)

**Interfaces:**
- Consumes: Task 6 (`MemoryStore`)
- Produces: `MemoryRetriever.retrieve(task_description: str, max_chars: int) -> str`

- [ ] **Step 1: 编写失败测试**

```python
# 追加到 tests/test_memory.py

from src.memory.retriever import MemoryRetriever


def test_retriever_returns_empty_for_empty_memory(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    retriever = MemoryRetriever(store)
    result = retriever.retrieve("fix the failing test", 500)
    assert result == ""


def test_retriever_includes_test_convention(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.save({
        "project": {"name": "demo"},
        "conventions": {"test_command": "python -m pytest -v"},
        "fix_history": [],
        "graylist_commands": [],
        "audit_log": [],
    })
    retriever = MemoryRetriever(store)
    result = retriever.retrieve("run tests", 500)
    assert "python -m pytest" in result


def test_retriever_matches_fix_history_by_error_type(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.add_fix_record({
        "error_type": "AssertionError",
        "file": "calc.py",
        "strategy": "修复返回值逻辑",
    })
    retriever = MemoryRetriever(store)
    result = retriever.retrieve("fix assertion error in test", 500)
    assert "AssertionError" in result
    assert "calc.py" in result


def test_retriever_respects_max_chars(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.save({
        "project": {"name": "demo"},
        "conventions": {"test_command": "python -m pytest -v", "lint_command": "flake8"},
        "fix_history": [],
        "graylist_commands": [],
        "audit_log": [],
    })
    retriever = MemoryRetriever(store)
    result = retriever.retrieve("run tests", max_chars=20)
    assert len(result) <= 20


def test_retriever_no_match_returns_empty(temp_harness_dir):
    store = MemoryStore(temp_harness_dir)
    store.add_fix_record({
        "error_type": "AssertionError",
        "file": "calc.py",
        "strategy": "修复返回值",
    })
    retriever = MemoryRetriever(store)
    result = retriever.retrieve("deploy to production", 500)
    assert result == "" or "AssertionError" not in result
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_memory.py::test_retriever_returns_empty_for_empty_memory -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/memory/retriever.py**

```python
from src.memory.store import MemoryStore


class MemoryRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def retrieve(self, task_description: str, max_chars: int = 1000) -> str:
        data = self.store.load()
        parts = []
        task_lower = task_description.lower()

        conventions = data.get("conventions", {})
        if conventions:
            parts.append("[项目约定]")
            if "test_command" in conventions:
                parts.append(f"测试命令: {conventions['test_command']}")
            if "lint_command" in conventions and conventions["lint_command"]:
                parts.append(f"Lint命令: {conventions['lint_command']}")

        fix_history = data.get("fix_history", [])
        if fix_history:
            keywords = self._extract_keywords(task_lower)
            matched = []
            for record in fix_history:
                record_text = f"{record.get('error_type', '')} {record.get('file', '')} {record.get('strategy', '')}".lower()
                if any(kw in record_text for kw in keywords) or not keywords:
                    matched.append(record)
            if matched:
                parts.append("[历史修复记录]")
                for r in matched[-3:]:
                    parts.append(
                        f"- {r.get('error_type')} @ {r.get('file')}: {r.get('strategy')}"
                    )

        result = "\n".join(parts)
        if len(result) > max_chars:
            result = result[:max_chars]
        return result

    def _extract_keywords(self, task: str) -> list[str]:
        keywords = []
        if "test" in task or "pytest" in task:
            keywords.append("test")
        if "assert" in task:
            keywords.extend(["assert", "assertion"])
        if "import" in task:
            keywords.append("import")
        if "syntax" in task:
            keywords.append("syntax")
        if "type" in task:
            keywords.append("type")
        if "attribute" in task:
            keywords.append("attribute")
        if "timeout" in task:
            keywords.append("timeout")
        return keywords
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_memory.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/memory/retriever.py tests/test_memory.py
git commit -m "feat: memory retriever with keyword matching"
```

---

### Task 8: 工具注册表 + 基础接口

**Files:**
- Create: `src/tools/registry.py`
- Create: `tests/test_tools.py`

**Interfaces:**
- Consumes: Task 1 (directory structure), Task 4 (config loader)
- Produces: `ToolRegistry` class with `register(tool)`, `execute(name, args) -> ToolResult`, `list_tools() -> list[dict]`, `ToolResult` dataclass

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_tools.py
import pytest
from pathlib import Path
from src.tools.registry import ToolRegistry, ToolResult


def test_tool_registry_register_and_list():
    registry = ToolRegistry()
    def dummy_tool(path: str) -> ToolResult:
        return ToolResult(success=True, output=f"read {path}")

    registry.register("read_file", dummy_tool, {"path": "str"})
    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "read_file"


def test_tool_registry_execute_success():
    registry = ToolRegistry()
    def echo(msg: str) -> ToolResult:
        return ToolResult(success=True, output=msg)

    registry.register("echo", echo, {"msg": "str"})
    result = registry.execute("echo", {"msg": "hello"})
    assert result.success is True
    assert result.output == "hello"


def test_tool_registry_execute_unknown_tool():
    registry = ToolRegistry()
    result = registry.execute("nonexistent", {})
    assert result.success is False
    assert "unknown" in result.output.lower()


def test_tool_registry_execute_missing_arg():
    registry = ToolRegistry()
    def greet(name: str) -> ToolResult:
        return ToolResult(success=True, output=f"hi {name}")

    registry.register("greet", greet, {"name": "str"})
    result = registry.execute("greet", {})
    assert result.success is False


def test_tool_registry_tool_count():
    registry = ToolRegistry()
    assert registry.tool_count == 0
    registry.register("t1", lambda: ToolResult(success=True, output=""), {})
    registry.register("t2", lambda: ToolResult(success=True, output=""), {})
    assert registry.tool_count == 2


def test_tool_result_defaults():
    r = ToolResult(success=True, output="ok")
    assert r.error is None
    assert r.exit_code == 0
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_tools.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/tools/registry.py**

```python
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    def register(self, name: str, func: Callable, params: dict[str, str]) -> None:
        self._tools[name] = {"func": func, "params": params}

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "parameters": info["params"]}
            for name, info in self._tools.items()
        ]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")

        tool = self._tools[name]
        try:
            return tool["func"](**args)
        except TypeError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_tools.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/tools/registry.py tests/test_tools.py
git commit -m "feat: tool registry with registration and execution"
```

---

### Task 9: 文件操作工具 (read_file, write_file, edit_file)

**Files:**
- Create: `src/tools/file_tools.py`
- Modify: `tests/test_tools.py` (追加测试)

**Interfaces:**
- Consumes: Task 8 (`ToolRegistry`, `ToolResult`)
- Produces: `read_file(path, start_line, end_line) -> ToolResult`, `write_file(path, content) -> ToolResult`, `edit_file(path, search, replace) -> ToolResult`

- [ ] **Step 1: 编写失败测试**

```python
# 追加到 tests/test_tools.py

from src.tools.file_tools import read_file, write_file, edit_file


def test_read_file_returns_content(temp_workspace):
    test_file = temp_workspace / "test.txt"
    test_file.write_text("line1\nline2\nline3")
    result = read_file(str(test_file))
    assert result.success is True
    assert "line1" in result.output


def test_read_file_with_line_range(temp_workspace):
    test_file = temp_workspace / "test.txt"
    test_file.write_text("line1\nline2\nline3\nline4")
    result = read_file(str(test_file), start_line=2, end_line=3)
    assert "line2" in result.output
    assert "line1" not in result.output


def test_read_file_not_found(temp_workspace):
    result = read_file(str(temp_workspace / "nonexistent.txt"))
    assert result.success is False


def test_write_file_creates_file(temp_workspace):
    path = str(temp_workspace / "new.txt")
    result = write_file(path, "hello world")
    assert result.success is True
    assert (temp_workspace / "new.txt").read_text() == "hello world"


def test_edit_file_replaces_text(temp_workspace):
    test_file = temp_workspace / "code.py"
    test_file.write_text("x = 1 + 2")
    result = edit_file(str(test_file), "1 + 2", "2 + 3")
    assert result.success is True
    assert test_file.read_text() == "x = 2 + 3"


def test_edit_file_search_not_found(temp_workspace):
    test_file = temp_workspace / "code.py"
    test_file.write_text("x = 1 + 2")
    result = edit_file(str(test_file), "not in file", "replacement")
    assert result.success is False
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_tools.py::test_read_file_returns_content -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/tools/file_tools.py**

```python
from pathlib import Path
from src.tools.registry import ToolResult


def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if start_line is not None:
            start = max(0, start_line - 1)
            end = min(len(lines), end_line) if end_line is not None else len(lines)
            lines = lines[start:end]
        return ToolResult(success=True, output="".join(lines))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def write_file(path: str, content: str) -> ToolResult:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(success=True, output=f"Written {len(content)} bytes to {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def edit_file(path: str, search: str, replace: str) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    try:
        content = p.read_text(encoding="utf-8")
        if search not in content:
            return ToolResult(success=False, output="", error=f"Search text not found in {path}")
        new_content = content.replace(search, replace, 1)
        p.write_text(new_content, encoding="utf-8")
        return ToolResult(success=True, output=f"Replaced 1 occurrence in {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_tools.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/tools/file_tools.py tests/test_tools.py
git commit -m "feat: file tools (read, write, edit)"
```

---

### Task 10: 搜索与执行工具 (grep, list_dir, run_shell)

**Files:**
- Create: `src/tools/search_tools.py`
- Create: `src/tools/shell_tools.py`
- Modify: `tests/test_tools.py` (追加测试)

**Interfaces:**
- Consumes: Task 8 (`ToolRegistry`, `ToolResult`)
- Produces: `grep(pattern, path) -> ToolResult`, `list_dir(path, depth) -> ToolResult`, `run_shell(command, timeout) -> ToolResult`

- [ ] **Step 1: 编写失败测试**

```python
# 追加到 tests/test_tools.py

from src.tools.search_tools import grep, list_dir
from src.tools.shell_tools import run_shell


def test_grep_finds_matches(temp_workspace):
    (temp_workspace / "code.py").write_text("def test_a():\n    pass\ndef test_b():\n    pass")
    result = grep(r"def test_", str(temp_workspace))
    assert result.success is True
    assert "test_a" in result.output
    assert "test_b" in result.output


def test_grep_no_matches(temp_workspace):
    (temp_workspace / "code.py").write_text("hello world")
    result = grep(r"def test_", str(temp_workspace))
    assert result.success is True
    assert result.output == ""


def test_list_dir_shows_contents(temp_workspace):
    (temp_workspace / "a.py").write_text("")
    (temp_workspace / "b.py").write_text("")
    (temp_workspace / "sub").mkdir()
    result = list_dir(str(temp_workspace))
    assert result.success is True
    assert "a.py" in result.output
    assert "b.py" in result.output
    assert "sub" in result.output


def test_list_dir_invalid_path():
    result = list_dir("/nonexistent/path")
    assert result.success is False


def test_run_shell_returns_output():
    result = run_shell("echo hello")
    assert result.success is True
    assert "hello" in result.output


def test_run_shell_failed_command():
    result = run_shell("python -c 'import sys; sys.exit(1)'")
    assert result.success is False
    assert result.exit_code == 1
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_tools.py::test_grep_finds_matches -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/tools/search_tools.py**

```python
import re
from pathlib import Path
from src.tools.registry import ToolResult


def grep(pattern: str, path: str) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"Path not found: {path}")
    try:
        matches = []
        if p.is_file():
            files = [p]
        else:
            files = list(p.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if re.search(pattern, line):
                        matches.append(f"{f}:{i}: {line}")
            except Exception:
                continue
        return ToolResult(success=True, output="\n".join(matches))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def list_dir(path: str, depth: int = 3) -> ToolResult:
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output="", error=f"Path not found: {path}")
    try:
        lines = []
        for item in sorted(p.iterdir()):
            prefix = "[D]" if item.is_dir() else "[F]"
            lines.append(f"{prefix} {item.name}")
        return ToolResult(success=True, output="\n".join(lines))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 4: 实现 src/tools/shell_tools.py**

```python
import subprocess
from src.tools.registry import ToolResult


def run_shell(command: str, timeout: int = 120) -> ToolResult:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return ToolResult(
            success=result.returncode == 0,
            output=output.strip() or "(no output)",
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            output="",
            error=f"Command timed out after {timeout}s",
            exit_code=-1,
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e), exit_code=-1)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_tools.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/tools/search_tools.py src/tools/shell_tools.py tests/test_tools.py
git commit -m "feat: search and shell tools (grep, list_dir, run_shell)"
```

---

### Task 11: 护栏分级 + 沙箱校验

**Files:**
- Create: `src/guardrail/classifier.py`
- Create: `src/guardrail/sandbox.py`
- Create: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: Task 1 (directory structure)
- Produces: `classify_action(tool_name, args) -> int` (返回 1/2/3), `Sandbox.verify_path(path, root) -> bool`, `InterceptResult` dataclass

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_guardrail.py
import pytest
from pathlib import Path
from src.guardrail.classifier import classify_action, InterceptResult
from src.guardrail.sandbox import Sandbox


def test_classify_read_file_level1():
    result = classify_action("read_file", {"path": "test.py"})
    assert result.level == 1
    assert result.blocked is False


def test_classify_grep_level1():
    result = classify_action("grep", {"pattern": "def", "path": "src/"})
    assert result.level == 1


def test_classify_list_dir_level1():
    result = classify_action("list_dir", {"path": "."})
    assert result.level == 1


def test_classify_write_file_level2():
    result = classify_action("write_file", {"path": "src/new.py", "content": "x=1"})
    assert result.level == 2
    assert result.blocked is False


def test_classify_run_shell_pytest_level1():
    result = classify_action("run_shell", {"command": "python -m pytest"})
    assert result.level == 1


def test_classify_run_shell_pip_install_level2():
    result = classify_action("run_shell", {"command": "pip install requests"})
    assert result.level == 2


def test_classify_run_shell_rm_rf_level3():
    result = classify_action("run_shell", {"command": "rm -rf /"})
    assert result.level == 3
    assert result.blocked is True


def test_classify_run_shell_git_push_force_level3():
    result = classify_action("run_shell", {"command": "git push --force origin main"})
    assert result.level == 3
    assert result.blocked is True


def test_classify_run_shell_drop_table_level3():
    result = classify_action("run_shell", {"command": "DROP TABLE users"})
    assert result.level == 3
    assert result.blocked is True


def test_classify_run_shell_chmod_777_level3():
    result = classify_action("run_shell", {"command": "chmod 777 /etc/passwd"})
    assert result.level == 3


def test_sandbox_verify_path_inside_root():
    sandbox = Sandbox(Path("/workspace"))
    assert sandbox.verify_path("/workspace/src/test.py") is True
    assert sandbox.verify_path("/workspace/sub/dir/file.txt") is True


def test_sandbox_verify_path_outside_root():
    sandbox = Sandbox(Path("/workspace"))
    assert sandbox.verify_path("/etc/passwd") is False
    assert sandbox.verify_path("../outside") is False


def test_sandbox_verify_path_absolute_outside():
    sandbox = Sandbox(Path("/workspace"))
    assert sandbox.verify_path("/home/user/file.txt") is False
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_guardrail.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/guardrail/classifier.py**

```python
import re
from dataclasses import dataclass


@dataclass
class InterceptResult:
    level: int
    blocked: bool
    reason: str = ""


LEVEL1_TOOLS = {"read_file", "grep", "list_dir"}
LEVEL1_COMMANDS = [
    re.compile(r"^(python|python3)\s+-m\s+pytest"),
    re.compile(r"^(python|python3)\s+-m\s+mypy"),
    re.compile(r"^(pytest|flake8|mypy|black|isort|ruff)"),
    re.compile(r"^(echo|cat|head|tail|ls|dir|pwd|whoami|date)"),
]
LEVEL3_PATTERNS = [
    (re.compile(r"\brm\s+-rf\b"), "rm -rf is destructive"),
    (re.compile(r"\brm\s+-r\b"), "rm -r is destructive"),
    (re.compile(r"\bgit\s+push\s+.*--force"), "git push --force is irreversible"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard is destructive"),
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "DROP TABLE is destructive"),
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "DROP DATABASE is destructive"),
    (re.compile(r"\bchmod\s+777\b"), "chmod 777 is a security risk"),
    (re.compile(r"\bchown\b"), "chown may be dangerous"),
    (re.compile(r"\b(shutdown|reboot|systemctl\s+stop)\b"), "system command is dangerous"),
    (re.compile(r"\bdel\s+/[fsq]\b"), "Windows destructive delete"),
    (re.compile(r"\bformat\s+[a-zA-Z]:\b", re.IGNORECASE), "disk format is destructive"),
]


def classify_action(tool_name: str, args: dict) -> InterceptResult:
    if tool_name in LEVEL1_TOOLS:
        return InterceptResult(level=1, blocked=False)

    if tool_name == "run_shell":
        command = args.get("command", "")

        for pattern, reason in LEVEL3_PATTERNS:
            if pattern.search(command):
                return InterceptResult(level=3, blocked=True, reason=reason)

        for pattern in LEVEL1_COMMANDS:
            if pattern.search(command):
                return InterceptResult(level=1, blocked=False)

        return InterceptResult(level=2, blocked=False, reason="Unclassified shell command")

    if tool_name in ("write_file", "edit_file"):
        return InterceptResult(level=2, blocked=False)

    return InterceptResult(level=2, blocked=False, reason=f"Unknown tool: {tool_name}")
```

- [ ] **Step 4: 实现 src/guardrail/sandbox.py**

```python
from pathlib import Path


class Sandbox:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def verify_path(self, target_path: str) -> bool:
        try:
            resolved = (self.root / target_path).resolve()
            return str(resolved).startswith(str(self.root))
        except (ValueError, OSError):
            return False
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_guardrail.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/guardrail/classifier.py src/guardrail/sandbox.py tests/test_guardrail.py
git commit -m "feat: guardrail classifier (3-level) and sandbox path verification"
```

---

### Task 12: HITL 状态机

**Files:**
- Create: `src/guardrail/hitl.py`
- Modify: `tests/test_guardrail.py` (追加测试)

**Interfaces:**
- Consumes: Task 11 (`InterceptResult`)
- Produces: `HITLStateMachine` class with `request_approval(result) -> HITLDecision` enum (ALLOW/DENY/ALWAYS)

- [ ] **Step 1: 编写失败测试**

```python
# 追加到 tests/test_guardrail.py

from src.guardrail.hitl import HITLStateMachine, HITLDecision
from unittest.mock import patch


def test_hitl_approve_returns_allow():
    hitl = HITLStateMachine()
    with patch("builtins.input", return_value="y"):
        decision = hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf"))
    assert decision == HITLDecision.ALLOW


def test_hitl_deny_returns_deny():
    hitl = HITLStateMachine()
    with patch("builtins.input", return_value="n"):
        decision = hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf"))
    assert decision == HITLDecision.DENY


def test_hitl_always_returns_always():
    hitl = HITLStateMachine()
    with patch("builtins.input", return_value="always"):
        decision = hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf"))
    assert decision == HITLDecision.ALWAYS


def test_hitl_invalid_then_valid_input():
    hitl = HITLStateMachine()
    with patch("builtins.input", side_effect=["invalid", "y"]):
        decision = hitl.request_approval(InterceptResult(level=3, blocked=True, reason="rm -rf"))
    assert decision == HITLDecision.ALLOW


def test_hitl_level2_no_confirm_bypass():
    hitl = HITLStateMachine()
    result = hitl.check(InterceptResult(level=2, blocked=False, reason="pip install"))
    assert result == HITLDecision.ALLOW


def test_hitl_level3_requires_confirm():
    hitl = HITLStateMachine()
    result = hitl.check(InterceptResult(level=3, blocked=True, reason="rm -rf"))
    assert result is None  # 需要交互确认，返回 None 表示等待
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_guardrail.py::test_hitl_approve_returns_allow -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/guardrail/hitl.py**

```python
from enum import Enum
from src.guardrail.classifier import InterceptResult


class HITLDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ALWAYS = "always"


class HITLStateMachine:
    def __init__(self):
        self.graylist: set[str] = set()

    def check(self, result: InterceptResult) -> HITLDecision | None:
        if result.level < 3:
            return HITLDecision.ALLOW
        return None  # 需要交互确认

    def request_approval(self, result: InterceptResult) -> HITLDecision:
        print(f"\n[HITL] Level {result.level} action blocked: {result.reason}")
        while True:
            choice = input("Allow? (y=yes / n=no / always=permanently allow): ").strip().lower()
            if choice == "y":
                return HITLDecision.ALLOW
            elif choice == "n":
                return HITLDecision.DENY
            elif choice == "always":
                return HITLDecision.ALWAYS
            else:
                print("Invalid input. Enter y, n, or always.")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_guardrail.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/guardrail/hitl.py tests/test_guardrail.py
git commit -m "feat: HITL state machine for guardrail approval"
```

---

### Task 13: 反馈解析器 + 失败分类器

**Files:**
- Create: `src/feedback/parser.py`
- Create: `src/feedback/classifier.py`
- Create: `tests/test_feedback.py`

**Interfaces:**
- Consumes: Task 1 (directory structure), Task 8 (`ToolResult`)
- Produces: `parse_test_output(output: str) -> list[dict]`, `classify_failure(failure: dict) -> str`, `FailureInfo` dataclass

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_feedback.py
import pytest
from src.feedback.parser import parse_test_output
from src.feedback.classifier import classify_failure, FailureInfo

PYTEST_FAIL_OUTPUT = """
============================= test session starts ==============================
test_calc.py::test_add FAILED
test_calc.py::test_sub PASSED

=================================== FAILURES ===================================
__________________________________ test_add ___________________________________

    def test_add():
>       assert calc.add(1, 2) == 4
E       assert 3 == 4
E        +  where 3 = calc.add(1, 2)

test_calc.py:5: AssertionError
========================= 1 failed, 1 passed in 0.12s =========================
"""


def test_parse_test_output_finds_failure():
    failures = parse_test_output(PYTEST_FAIL_OUTPUT)
    assert len(failures) == 1
    assert failures[0]["file"] == "test_calc.py"
    assert "assert" in failures[0]["message"].lower()


def test_parse_test_output_empty():
    assert parse_test_output("") == []


def test_parse_test_output_all_pass():
    output = "3 passed in 0.10s"
    assert parse_test_output(output) == []


def test_classify_failure_assertion_error():
    info = classify_failure({
        "file": "test_calc.py",
        "line": 5,
        "message": "assert 3 == 4\nAssertionError",
    })
    assert info.type == "AssertionError"
    assert "期望值" in info.strategy


def test_classify_failure_syntax_error():
    info = classify_failure({
        "file": "calc.py",
        "line": 10,
        "message": "SyntaxError: invalid syntax",
    })
    assert info.type == "SyntaxError"


def test_classify_failure_import_error():
    info = classify_failure({
        "file": "test.py",
        "line": 1,
        "message": "ModuleNotFoundError: No module named 'requests'",
    })
    assert info.type == "ImportError"


def test_classify_failure_attribute_error():
    info = classify_failure({
        "file": "calc.py",
        "line": 8,
        "message": "AttributeError: 'int' object has no attribute 'add'",
    })
    assert info.type == "AttributeError"


def test_classify_failure_type_error():
    info = classify_failure({
        "file": "calc.py",
        "line": 5,
        "message": "TypeError: unsupported operand type(s) for +",
    })
    assert info.type == "TypeError"


def test_classify_failure_timeout():
    info = classify_failure({
        "file": "",
        "line": None,
        "message": "Command timed out after 120s",
    })
    assert info.type == "Timeout"


def test_classify_failure_unknown():
    info = classify_failure({
        "file": "x.py",
        "line": 1,
        "message": "some weird error we have never seen before",
    })
    assert info.type == "UnknownError"
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_feedback.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/feedback/parser.py**

```python
import re


def parse_test_output(output: str) -> list[dict]:
    failures = []
    if not output:
        return failures

    fail_pattern = re.compile(r"^(.+?)\s+FAILED", re.MULTILINE)
    fail_files = fail_pattern.findall(output)

    failure_section = re.split(r"=+\s+FAILURES\s+=+", output)
    if len(failure_section) < 2:
        return failures

    failure_text = failure_section[1]

    test_sections = re.split(r"_+\s+(\w+)\s+_+", failure_text)

    for fname in fail_files:
        fname_clean = fname.strip()
        failure_info = {
            "file": fname_clean.split("::")[0] if "::" in fname_clean else fname_clean,
            "line": None,
            "message": "",
        }

        line_match = re.search(rf"{re.escape(fname_clean)}.*?:(\d+):", failure_text)
        if line_match:
            failure_info["line"] = int(line_match.group(1))

        failure_info["message"] = failure_text[:500].strip()

        failures.append(failure_info)

    return failures
```

- [ ] **Step 4: 实现 src/feedback/classifier.py**

```python
import re
from dataclasses import dataclass


@dataclass
class FailureInfo:
    type: str
    file: str
    line: int | None
    message: str
    expected: str | None = None
    actual: str | None = None
    strategy: str = ""


CLASSIFICATION_RULES = [
    (re.compile(r"SyntaxError|IndentationError", re.IGNORECASE), "SyntaxError",
     "定位报错行号，检查语法和缩进错误"),
    (re.compile(r"ModuleNotFoundError|ImportError", re.IGNORECASE), "ImportError",
     "检查包名拼写以及依赖是否已安装"),
    (re.compile(r"AssertionError", re.IGNORECASE), "AssertionError",
     "对比期望值与实际值差异，检查被测试函数的实现逻辑"),
    (re.compile(r"AttributeError", re.IGNORECASE), "AttributeError",
     "检查对象类型，确认属性或方法名拼写是否正确"),
    (re.compile(r"TypeError", re.IGNORECASE), "TypeError",
     "检查函数参数类型和数量是否匹配"),
    (re.compile(r"timed?[\s-]*out", re.IGNORECASE), "Timeout",
     "命令执行超时，建议优化代码或增加超时时间"),
]


def classify_failure(failure: dict) -> FailureInfo:
    message = failure.get("message", "")
    for pattern, error_type, strategy in CLASSIFICATION_RULES:
        if pattern.search(message):
            return FailureInfo(
                type=error_type,
                file=failure.get("file", ""),
                line=failure.get("line"),
                message=message,
                strategy=strategy,
            )

    return FailureInfo(
        type="UnknownError",
        file=failure.get("file", ""),
        line=failure.get("line"),
        message=message,
        strategy="原文回灌，由 LLM 自主分析",
    )
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_feedback.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/feedback/parser.py src/feedback/classifier.py tests/test_feedback.py
git commit -m "feat: feedback parser and failure classifier (8 types)"
```

---

### Task 14: 反馈构建器

**Files:**
- Create: `src/feedback/builder.py`
- Modify: `tests/test_feedback.py` (追加测试)

**Interfaces:**
- Consumes: Task 13 (`parse_test_output`, `classify_failure`, `FailureInfo`)
- Produces: `build_feedback(test_output: str, previous_test_output: str | None) -> FeedbackResult`

- [ ] **Step 1: 编写失败测试**

```python
# 追加到 tests/test_feedback.py

from src.feedback.builder import build_feedback, FeedbackResult


def test_build_feedback_with_failure():
    output = """
test_calc.py::test_add FAILED
============================= FAILURES =============================
assert 3 == 4
AssertionError
"""
    result = build_feedback(output)
    assert result.test_result == "FAIL"
    assert len(result.failures) == 1
    assert result.failures[0].type == "AssertionError"
    assert "1/1" in result.summary


def test_build_feedback_all_pass():
    output = "3 passed in 0.10s"
    result = build_feedback(output)
    assert result.test_result == "PASS"
    assert len(result.failures) == 0


def test_build_feedback_detects_regression():
    previous = "test_calc.py::test_add PASSED\n3 passed in 0.10s"
    current = """
test_calc.py::test_add FAILED
============================= FAILURES =============================
assert 3 == 4
AssertionError
"""
    result = build_feedback(current, previous)
    assert result.regression is True


def test_build_feedback_no_regression_without_previous():
    output = "test_calc.py::test_add FAILED"
    result = build_feedback(output, None)
    assert result.regression is False
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_feedback.py::test_build_feedback_with_failure -v
# Expected: FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/feedback/builder.py**

```python
from dataclasses import dataclass, field
from src.feedback.parser import parse_test_output
from src.feedback.classifier import classify_failure, FailureInfo


@dataclass
class FeedbackResult:
    test_result: str  # "PASS" | "FAIL" | "TIMEOUT" | "ERROR"
    failures: list[FailureInfo] = field(default_factory=list)
    summary: str = ""
    regression: bool = False


def build_feedback(test_output: str, previous_test_output: str | None = None) -> FeedbackResult:
    raw_failures = parse_test_output(test_output)

    if not raw_failures:
        return FeedbackResult(test_result="PASS", summary="All tests passed")

    failures = [classify_failure(f) for f in raw_failures]

    total = len(raw_failures)
    failure_names = [f.file for f in raw_failures]
    summary = f"{total} tests failed: {', '.join(failure_names)}"

    regression = False
    if previous_test_output:
        prev_failures = parse_test_output(previous_test_output)
        prev_files = {f.get("file") for f in prev_failures}
        for f in raw_failures:
            if f.get("file") not in prev_files:
                regression = True
                break

    return FeedbackResult(
        test_result="FAIL",
        failures=failures,
        summary=summary,
        regression=regression,
    )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_feedback.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/feedback/builder.py tests/test_feedback.py
git commit -m "feat: feedback builder with regression detection"
```

---

### Task 15: Agent 主循环 + 停机判断

**Files:**
- Create: `src/agent_loop/loop.py`
- Create: `src/agent_loop/stop_judge.py`
- Create: `tests/test_loop.py`

**Interfaces:**
- Consumes: Task 2, 3, 4, 6, 7, 8, 11, 12, 13, 14
- Produces: `AgentLoop.run(task: str) -> LoopResult`, `StopJudge.should_stop(state) -> StopReason`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_loop.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.agent_loop.stop_judge import StopJudge, StopReason
from src.agent_loop.loop import AgentLoop, LoopResult
from src.llm.base import LLMResponse, ToolCall
from src.llm.mock import MockLLM
from src.tools.registry import ToolRegistry, ToolResult
from src.guardrail.classifier import InterceptResult
from src.guardrail.hitl import HITLStateMachine, HITLDecision


def test_stop_judge_test_pass():
    judge = StopJudge(max_iterations=10)
    reason = judge.should_stop(iteration=3, test_passed=True, llm_text="done", tool_calls=None)
    assert reason == StopReason.TEST_PASSED


def test_stop_judge_max_iterations():
    judge = StopJudge(max_iterations=5)
    reason = judge.should_stop(iteration=5, test_passed=False, llm_text=None, tool_calls=[ToolCall(name="grep", args={})])
    assert reason == StopReason.MAX_ITERATIONS


def test_stop_judge_llm_stopped():
    judge = StopJudge(max_iterations=10)
    reason = judge.should_stop(iteration=2, test_passed=False, llm_text="Task complete.", tool_calls=None)
    assert reason == StopReason.LLM_STOPPED


def test_stop_judge_dead_loop():
    judge = StopJudge(max_iterations=10)
    for _ in range(4):
        reason = judge.should_stop(iteration=3, test_passed=False, llm_text=None, tool_calls=[ToolCall(name="grep", args={"pattern": "test"})])
    assert reason == StopReason.DEAD_LOOP


def test_stop_judge_continue():
    judge = StopJudge(max_iterations=10)
    reason = judge.should_stop(iteration=2, test_passed=False, llm_text=None, tool_calls=[ToolCall(name="grep", args={})])
    assert reason is None


def test_agent_loop_completes_with_mock_llm(temp_workspace):
    mock = MockLLM(responses=[
        LLMResponse(tool_calls=[ToolCall(name="run_shell", args={"command": "python -m pytest"})]),
        LLMResponse(text="All tests pass! Task complete."),
    ])
    registry = ToolRegistry()
    def fake_shell(command, timeout=120):
        if "pytest" in command:
            return ToolResult(success=True, output="3 passed in 0.10s", exit_code=0)
        return ToolResult(success=True, output="ok")
    registry.register("run_shell", fake_shell, {"command": "str", "timeout": "int"})

    with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
        mock_hitl = MagicMock()
        mock_hitl.check.return_value = HITLDecision.ALLOW
        mock_hitl_cls.return_value = mock_hitl

        loop = AgentLoop(
            llm=mock,
            tools=registry,
            workspace=temp_workspace,
            config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
        )
        result = loop.run("fix the failing tests")

    assert result.success is True
    assert mock.call_count == 2


def test_agent_loop_respects_max_iterations(temp_workspace):
    responses = []
    for _ in range(5):
        responses.append(LLMResponse(tool_calls=[ToolCall(name="grep", args={"pattern": "test", "path": "."})]))
    mock = MockLLM(responses=responses)

    registry = ToolRegistry()
    registry.register("grep", lambda pattern, path: ToolResult(success=True, output=""), {"pattern": "str", "path": "str"})

    with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
        mock_hitl = MagicMock()
        mock_hitl.check.return_value = HITLDecision.ALLOW
        mock_hitl_cls.return_value = mock_hitl

        loop = AgentLoop(
            llm=mock,
            tools=registry,
            workspace=temp_workspace,
            config={"max_iterations": 3, "timeout": 120, "test_command": "pytest", "sandbox_root": str(temp_workspace)},
        )
        result = loop.run("fix the failing tests")

    assert result.success is False
    assert result.stop_reason == "max_iterations"
    assert mock.call_count <= 3
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_loop.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/agent_loop/stop_judge.py**

```python
from enum import Enum
from collections import defaultdict


class StopReason(Enum):
    TEST_PASSED = "test_passed"
    MAX_ITERATIONS = "max_iterations"
    LLM_STOPPED = "llm_stopped"
    DEAD_LOOP = "dead_loop"


class StopJudge:
    def __init__(self, max_iterations: int = 10, dead_loop_threshold: int = 3):
        self.max_iterations = max_iterations
        self.dead_loop_threshold = dead_loop_threshold
        self._tool_call_history: list[frozenset] = []

    def should_stop(self, iteration: int, test_passed: bool, llm_text: str | None, tool_calls: list | None) -> StopReason | None:
        if test_passed:
            return StopReason.TEST_PASSED

        if iteration >= self.max_iterations:
            return StopReason.MAX_ITERATIONS

        if llm_text and not tool_calls:
            return StopReason.LLM_STOPPED

        if tool_calls:
            call_pattern = frozenset((tc.name, frozenset(tc.args.items()) if hasattr(tc, 'args') else frozenset()) for tc in tool_calls)
            self._tool_call_history.append(call_pattern)
            if len(self._tool_call_history) >= self.dead_loop_threshold + 1:
                recent = self._tool_call_history[-self.dead_loop_threshold:]
                if all(r == recent[0] for r in recent):
                    return StopReason.DEAD_LOOP

        return None
```

- [ ] **Step 4: 实现 src/agent_loop/loop.py**

```python
from dataclasses import dataclass, field
from pathlib import Path
from src.llm.base import LLMBackend, LLMResponse
from src.tools.registry import ToolRegistry, ToolResult
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
                break

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
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_loop.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/agent_loop/stop_judge.py src/agent_loop/loop.py tests/test_loop.py
git commit -m "feat: agent main loop with stop judge"
```

---

### Task 16: CLI 入口

**Files:**
- Create: `src/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 15 (`AgentLoop`), all previous tasks
- Produces: CLI commands: `harness run`, `harness memory list/clear/set`, `harness keyring status/set/clear`, `harness config show`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_cli.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.cli import build_parser


def test_parser_run_command():
    parser = build_parser()
    args = parser.parse_args(["run", "fix the bug"])
    assert args.command == "run"
    assert args.task == "fix the bug"


def test_parser_memory_list():
    parser = build_parser()
    args = parser.parse_args(["memory", "list"])
    assert args.command == "memory"
    assert args.subcommand == "list"


def test_parser_memory_clear():
    parser = build_parser()
    args = parser.parse_args(["memory", "clear"])
    assert args.subcommand == "clear"


def test_parser_memory_set():
    parser = build_parser()
    args = parser.parse_args(["memory", "set", "test_command", "pytest -x"])
    assert args.subcommand == "set"
    assert args.key == "test_command"
    assert args.value == "pytest -x"


def test_parser_keyring_status():
    parser = build_parser()
    args = parser.parse_args(["keyring", "status"])
    assert args.command == "keyring"
    assert args.subcommand == "status"


def test_parser_keyring_set():
    parser = build_parser()
    args = parser.parse_args(["keyring", "set"])
    assert args.subcommand == "set"


def test_parser_config_show():
    parser = build_parser()
    args = parser.parse_args(["config", "show"])
    assert args.command == "config"
    assert args.subcommand == "show"
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_cli.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 src/cli.py**

```python
import argparse
import sys
import json
from pathlib import Path
from src.config.loader import load_config, DEFAULT_CONFIG
from src.config.keyring import set_api_key, key_status, clear_api_key
from src.memory.store import MemoryStore
from src.llm.real import RealLLM
from src.llm.mock import MockLLM
from src.tools.registry import ToolRegistry
from src.tools.file_tools import read_file, write_file, edit_file
from src.tools.search_tools import grep, list_dir
from src.tools.shell_tools import run_shell
from src.agent_loop.loop import AgentLoop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness", description="Coding Agent Harness")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run the agent")
    run_parser.add_argument("task", help="Task description")

    mem_parser = sub.add_parser("memory", help="Manage project memory")
    mem_sub = mem_parser.add_subparsers(dest="subcommand")
    mem_sub.add_parser("list", help="List memory entries")
    mem_sub.add_parser("clear", help="Clear all memory")
    mem_set = mem_sub.add_parser("set", help="Set a convention")
    mem_set.add_argument("key", help="Convention key")
    mem_set.add_argument("value", help="Convention value")

    key_parser = sub.add_parser("keyring", help="Manage API key")
    key_sub = key_parser.add_subparsers(dest="subcommand")
    key_sub.add_parser("status", help="Show key status")
    key_sub.add_parser("set", help="Set API key")
    key_sub.add_parser("clear", help="Clear API key")

    cfg_parser = sub.add_parser("config", help="Manage configuration")
    cfg_sub = cfg_parser.add_subparsers(dest="subcommand")
    cfg_sub.add_parser("show", help="Show current config")

    return parser


def cmd_run(args):
    cwd = Path.cwd()
    config = load_config(cwd)
    harness_dir = cwd / ".harness"
    harness_dir.mkdir(exist_ok=True)

    registry = ToolRegistry()
    registry.register("read_file", read_file, {"path": "str", "start_line": "int?", "end_line": "int?"})
    registry.register("write_file", write_file, {"path": "str", "content": "str"})
    registry.register("edit_file", edit_file, {"path": "str", "search": "str", "replace": "str"})
    registry.register("grep", grep, {"pattern": "str", "path": "str"})
    registry.register("list_dir", list_dir, {"path": "str"})
    registry.register("run_shell", run_shell, {"command": "str", "timeout": "int?"})

    llm = RealLLM(config)

    loop = AgentLoop(llm=llm, tools=registry, workspace=cwd, config=config)
    result = loop.run(args.task)

    print(f"\nResult: {'SUCCESS' if result.success else 'FAILED'} ({result.stop_reason})")
    print(f"Iterations: {result.iterations}")
    for log in result.logs:
        print(f"  {log}")


def cmd_memory(args):
    cwd = Path.cwd()
    store = MemoryStore(cwd / ".harness")

    if args.subcommand == "list":
        data = store.load()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.subcommand == "clear":
        store.clear()
        print("Memory cleared.")
    elif args.subcommand == "set":
        data = store.load()
        data["conventions"][args.key] = args.value
        store.save(data)
        print(f"Set {args.key} = {args.value}")


def cmd_keyring(args):
    if args.subcommand == "status":
        print(f"API key: {key_status()}")
    elif args.subcommand == "set":
        set_api_key()
        print("API key saved.")
    elif args.subcommand == "clear":
        clear_api_key()
        print("API key cleared.")


def cmd_config(args):
    if args.subcommand == "show":
        cwd = Path.cwd()
        config = load_config(cwd)
        print(json.dumps(config, ensure_ascii=False, indent=2))


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "memory":
        cmd_memory(args)
    elif args.command == "keyring":
        cmd_keyring(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_cli.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: CLI entry point (run, memory, keyring, config)"
```

---

### Task 17: Web 仪表盘

**Files:**
- Create: `web/app.py`
- Create: `tests/test_web.py`

**Interfaces:**
- Consumes: Task 6 (`MemoryStore`), Task 4 (`load_config`)
- Produces: FastAPI app with `GET /` (dashboard), `GET /api/status`, `GET /api/memory`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_web.py
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch
from web.app import create_app


@pytest.fixture
def client(temp_workspace):
    app = create_app(temp_workspace)
    return TestClient(app)


def test_dashboard_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_api_status_returns_json(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "workspace" in data
    assert "status" in data


def test_api_memory_returns_json(client):
    response = client.get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert "fix_history" in data
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_web.py -v
# Expected: all FAIL (ImportError)
```

- [ ] **Step 3: 实现 web/app.py**

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from src.memory.store import MemoryStore


def create_app(workspace: Path | None = None) -> FastAPI:
    app = FastAPI(title="Harness Dashboard")

    if workspace is None:
        workspace = Path.cwd()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        store = MemoryStore(workspace / ".harness")
        data = store.load()
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Harness Dashboard</title>
        <style>body{{font-family:monospace;max-width:800px;margin:40px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}}
        pre{{background:#16213e;padding:15px;border-radius:8px;overflow-x:auto}}
        .card{{background:#16213e;padding:15px;border-radius:8px;margin:10px 0}}</style></head>
        <body>
        <h1>Harness Dashboard</h1>
        <div class="card"><h3>Status</h3><p>Workspace: {workspace}</p></div>
        <div class="card"><h3>Project</h3><pre>{_format_json(data.get("project", {}))}</pre></div>
        <div class="card"><h3>Conventions</h3><pre>{_format_json(data.get("conventions", {}))}</pre></div>
        <div class="card"><h3>Fix History ({len(data.get("fix_history", []))} records)</h3><pre>{_format_json(data.get("fix_history", [])[-5:])}</pre></div>
        <div class="card"><h3>Audit Log ({len(data.get("audit_log", []))} entries)</h3><pre>{_format_json(data.get("audit_log", [])[-10:])}</pre></div>
        </body></html>"""

    @app.get("/api/status")
    async def api_status():
        return {"workspace": str(workspace), "status": "running"}

    @app.get("/api/memory")
    async def api_memory():
        store = MemoryStore(workspace / ".harness")
        return store.load()

    return app


def _format_json(data, indent=2):
    import json
    return json.dumps(data, ensure_ascii=False, indent=indent, default=str)


app = create_app()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_web.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add web/app.py tests/test_web.py
git commit -m "feat: FastAPI web dashboard"
```

---

### Task 18: Docker + CI/CD

**Files:**
- Create: `Dockerfile`
- Create: `.github/workflows/unit-test.yml`
- Create: `setup.py`

**Interfaces:**
- Consumes: all previous tasks
- Produces: Docker image, GitHub Actions CI pipeline

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.13-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY web/ web/
COPY setup.py .

RUN pip install -e .

ENTRYPOINT ["python", "-m", "src.cli"]
```

- [ ] **Step 2: 创建 setup.py**

```python
from setuptools import setup, find_packages

setup(
    name="harness",
    version="0.1.0",
    packages=find_packages(include=["src", "src.*"]),
    install_requires=[
        "pytest>=8.0",
        "fastapi>=0.115",
        "uvicorn>=0.30",
        "keyring>=25.0",
    ],
    entry_points={
        "console_scripts": [
            "harness=src.cli:main",
        ],
    },
)
```

- [ ] **Step 3: 创建 .github/workflows/unit-test.yml**

```yaml
name: unit-test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python -m pytest tests/ -v

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t harness .
```

- [ ] **Step 4: 本地验证 Docker 构建**

```bash
docker build -t harness .
docker run harness run "echo test"
```

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .github/workflows/unit-test.yml setup.py
git commit -m "feat: Dockerfile and GitHub Actions CI"
```

---

### Task 19: 机制演示脚本

**Files:**
- Create: `demo/test_guardrail_demo.py`
- Create: `demo/test_feedback_loop_demo.py`
- Create: `demo/test_classifier_demo.py`

**Interfaces:**
- Consumes: Task 11, 13, 14, 15
- Produces: 三个可独立运行的演示脚本，在 mock LLM 下确定性复现

- [ ] **Step 1: 创建 demo/__init__.py**

```bash
mkdir -p demo
touch demo/__init__.py
```

- [ ] **Step 2: 创建 demo/test_guardrail_demo.py**（演示①：护栏拦截危险动作）

```python
"""
机制演示 ①：治理护栏拦截危险动作
在 mock LLM 下确定性复现：agent 尝试执行 rm -rf → 被护栏拦截 → 等待人工确认
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.guardrail.classifier import classify_action


def demo():
    print("=" * 60)
    print("机制演示 ①：护栏拦截危险动作")
    print("=" * 60)

    # 安全命令
    safe = classify_action("run_shell", {"command": "python -m pytest"})
    print(f"\n[Safe] pytest: level={safe.level}, blocked={safe.blocked}")

    # 危险命令
    dangerous = classify_action("run_shell", {"command": "rm -rf /"})
    print(f"[Danger] rm -rf: level={dangerous.level}, blocked={dangerous.blocked}, reason={dangerous.reason}")

    # 更多危险命令
    for cmd in ["git push --force origin main", "DROP TABLE users", "chmod 777 /etc/passwd"]:
        result = classify_action("run_shell", {"command": cmd})
        print(f"[Danger] {cmd}: level={result.level}, blocked={result.blocked}")

    assert dangerous.level == 3
    assert dangerous.blocked is True
    print("\n✅ 护栏拦截演示通过：危险命令被正确拦截")


if __name__ == "__main__":
    demo()
```

- [ ] **Step 3: 创建 demo/test_feedback_loop_demo.py**（演示②：反馈闭环驱动修正）

```python
"""
机制演示 ②：反馈闭环使 agent 收到反馈后改变下一步动作
注入一次测试失败 → 反馈闭环解析分类 → 结构化反馈回灌 → agent 根据反馈改变行为
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.mock import MockLLM
from src.llm.base import LLMResponse, ToolCall
from src.tools.registry import ToolRegistry, ToolResult
from src.agent_loop.loop import AgentLoop
from unittest.mock import patch, MagicMock
from src.guardrail.hitl import HITLDecision


def demo():
    print("=" * 60)
    print("机制演示 ②：反馈闭环驱动自我修正")
    print("=" * 60)

    mock = MockLLM(responses=[
        LLMResponse(tool_calls=[ToolCall(name="run_shell", args={"command": "python -m pytest"})]),
        LLMResponse(tool_calls=[ToolCall(name="read_file", args={"path": "test_calc.py"})]),
        LLMResponse(tool_calls=[ToolCall(name="edit_file", args={"path": "calc.py", "search": "return a - b", "replace": "return a + b"})]),
        LLMResponse(text="Fixed! All tests should pass now."),
    ])

    registry = ToolRegistry()
    call_count = {"count": 0}

    def fake_shell(command, timeout=120):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return ToolResult(success=False, output="""test_calc.py::test_add FAILED
==================================== FAILURES ====================================
assert calc.add(1, 2) == 3
AssertionError: assert 3 == 4""", exit_code=1)
        return ToolResult(success=True, output="3 passed in 0.10s", exit_code=0)

    registry.register("run_shell", fake_shell, {"command": "str", "timeout": "int?"})
    registry.register("read_file", lambda path: ToolResult(success=True, output="def add(a,b): return a-b"), {"path": "str"})
    registry.register("edit_file", lambda path, search, replace: ToolResult(success=True, output="replaced"), {"path": "str", "search": "str", "replace": "str"})

    with patch("src.agent_loop.loop.HITLStateMachine") as mock_hitl_cls:
        mock_hitl = MagicMock()
        mock_hitl.check.return_value = HITLDecision.ALLOW
        mock_hitl_cls.return_value = mock_hitl

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".harness").mkdir()
            loop = AgentLoop(
                llm=mock,
                tools=registry,
                workspace=workspace,
                config={"max_iterations": 10, "timeout": 120, "test_command": "pytest", "sandbox_root": str(workspace)},
            )
            result = loop.run("fix the failing tests")

    print(f"\nResult: success={result.success}, stop_reason={result.stop_reason}")
    print(f"Iterations: {result.iterations}")
    assert mock.call_count >= 2, "Agent should make at least 2 LLM calls"
    print("\n✅ 反馈闭环演示通过：测试失败 → 分类 → 回灌 → agent 调整行为")


if __name__ == "__main__":
    demo()
```

- [ ] **Step 4: 创建 demo/test_classifier_demo.py**（演示③：失败分类器 8 种类型全覆盖）

```python
"""
机制演示 ③：失败分类器 8 种类型全覆盖
确定性复现：每种失败类型输入 → 分类器正确识别 → 策略映射正确
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feedback.classifier import classify_failure


def demo():
    print("=" * 60)
    print("机制演示 ③：失败分类器 8 种类型全覆盖")
    print("=" * 60)

    test_cases = [
        ({"file": "calc.py", "line": 10, "message": "SyntaxError: invalid syntax"}, "SyntaxError"),
        ({"file": "calc.py", "line": 10, "message": "IndentationError: unexpected indent"}, "SyntaxError"),
        ({"file": "test.py", "line": 1, "message": "ModuleNotFoundError: No module named 'x'"}, "ImportError"),
        ({"file": "test.py", "line": 1, "message": "ImportError: cannot import name 'foo'"}, "ImportError"),
        ({"file": "test_calc.py", "line": 5, "message": "assert 3 == 4\nAssertionError"}, "AssertionError"),
        ({"file": "calc.py", "line": 8, "message": "AttributeError: 'int' object has no attribute 'add'"}, "AttributeError"),
        ({"file": "calc.py", "line": 5, "message": "TypeError: unsupported operand type(s) for +"}, "TypeError"),
        ({"file": "", "line": None, "message": "Command timed out after 120s"}, "Timeout"),
        ({"file": "x.py", "line": 1, "message": "weird unknown error XYZ"}, "UnknownError"),
    ]

    all_passed = True
    for failure, expected_type in test_cases:
        info = classify_failure(failure)
        status = "✅" if info.type == expected_type else "❌"
        if info.type != expected_type:
            all_passed = False
        print(f"  {status} {failure['message'][:60]:60s} → {info.type} (expected: {expected_type})")

    print(f"\n{'✅ 全部 8 种分类通过' if all_passed else '❌ 有分类失败'}")
    assert all_passed, "All classification types must match"


if __name__ == "__main__":
    demo()
```

- [ ] **Step 5: 运行所有演示脚本验证**

```bash
python demo/test_guardrail_demo.py
python demo/test_feedback_loop_demo.py
python demo/test_classifier_demo.py
```

- [ ] **Step 6: Commit**

```bash
git add demo/ tests/
git commit -m "feat: mechanism demo scripts (guardrail, feedback loop, classifier)"
```

---

## 任务总结

| Task | 模块 | 可并行 | 预估时间 |
|------|------|--------|----------|
| 1 | 项目脚手架 | — | 5min |
| 2 | LLM 抽象基类 | 与 3 并行 | 10min |
| 3 | MockLLM | 与 2 并行 | 10min |
| 3.5 | RealLLM (njusehub) | 依赖 2, 5 | 15min |
| 4 | 配置加载器 | 与 5-7 并行 | 10min |
| 5 | 凭据管理 | 与 4,6,7 并行 | 10min |
| 6 | 记忆存储+过滤 | 与 4,5,7 并行 | 15min |
| 7 | 记忆检索器 | 与 4-6 并行 | 10min |
| 8 | 工具注册表 | 与 11-14 并行 | 10min |
| 9 | 文件操作工具 | 依赖 8 | 10min |
| 10 | 搜索+执行工具 | 依赖 8 | 10min |
| 11 | 护栏+沙箱 | 与 8-10,13-14 并行 | 15min |
| 12 | HITL 状态机 | 依赖 11 | 10min |
| 13 | 反馈解析+分类 | 依赖 8 (ToolResult) | 15min |
| 14 | 反馈构建器 | 依赖 13 | 10min |
| 15 | Agent 主循环 | 依赖 2-14 | 20min |
| 16 | CLI 入口 | 依赖 15 | 15min |
| 17 | Web 仪表盘 | 依赖 6 | 10min |
| 18 | Docker + CI | 依赖全部 | 10min |
| 19 | 机制演示 | 依赖 11,13,14,15 | 15min |

**总预估时间**: 约 4-5 小时（含 TDD 红绿重构循环）