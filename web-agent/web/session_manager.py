import secrets
import time
import shutil
import tempfile
from pathlib import Path
from src.agent_loop.loop import AgentLoop
from src.llm.real import RealLLM
from src.tools.registry import ToolRegistry
from src.tools.file_tools import read_file, write_file, edit_file
from src.tools.search_tools import grep, list_dir
from src.tools.shell_tools import run_shell
from src.guardrail.hitl import HITLStateMachine


class SessionManager:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir or tempfile.mkdtemp(prefix="harness_sessions_"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, dict] = {}
        self._registry = self._build_registry()

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register("read_file", read_file, {"path": "str", "start_line": "int?", "end_line": "int?"})
        registry.register("write_file", write_file, {"path": "str", "content": "str"})
        registry.register("edit_file", edit_file, {"path": "str", "search": "str", "replace": "str"})
        registry.register("grep", grep, {"pattern": "str", "path": "str"})
        registry.register("list_dir", list_dir, {"path": "str"})
        registry.register("run_shell", run_shell, {"command": "str", "timeout": "int?"})
        return registry

    def create_session(self, api_key: str) -> str:
        session_id = secrets.token_hex(16)
        workspace = self.base_dir / session_id
        workspace.mkdir(parents=True, exist_ok=True)
        llm = RealLLM({}, api_key=api_key)
        loop = AgentLoop(llm=llm, tools=self._registry, workspace=workspace, config={})
        loop.hitl = HITLStateMachine(web_mode=True, timeout=60)
        self._sessions[session_id] = {
            "workspace": workspace,
            "loop": loop,
            "llm": llm,
            "created_at": time.time(),
        }
        return session_id

    def get_loop(self, session_id: str) -> AgentLoop:
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")
        return self._sessions[session_id]["loop"]

    def get_workspace(self, session_id: str) -> Path:
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")
        return self._sessions[session_id]["workspace"]

    def destroy_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            ws = self._sessions[session_id]["workspace"]
            if ws.exists():
                shutil.rmtree(ws, ignore_errors=True)
            del self._sessions[session_id]

    def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s["created_at"] > max_age_seconds
        ]
        for sid in expired:
            self.destroy_session(sid)
        return len(expired)