import pytest
import tempfile
import time
from pathlib import Path
from web.session_manager import SessionManager


@pytest.fixture
def session_manager():
    with tempfile.TemporaryDirectory() as tmp:
        yield SessionManager(base_dir=Path(tmp))


def test_create_session_returns_id(session_manager):
    sid = session_manager.create_session(api_key="sk-test")
    assert sid
    assert len(sid) == 32


def test_create_session_creates_workspace(session_manager):
    sid = session_manager.create_session(api_key="sk-test")
    ws = session_manager.get_workspace(sid)
    assert ws.exists()
    assert ws.is_dir()


def test_get_loop_returns_agent_loop(session_manager):
    from src.agent_loop.loop import AgentLoop
    sid = session_manager.create_session(api_key="sk-test")
    loop = session_manager.get_loop(sid)
    assert isinstance(loop, AgentLoop)


def test_sessions_are_isolated(session_manager):
    sid1 = session_manager.create_session(api_key="sk-a")
    sid2 = session_manager.create_session(api_key="sk-b")
    ws1 = session_manager.get_workspace(sid1)
    ws2 = session_manager.get_workspace(sid2)
    assert ws1 != ws2


def test_destroy_session_removes_workspace(session_manager):
    sid = session_manager.create_session(api_key="sk-test")
    ws = session_manager.get_workspace(sid)
    session_manager.destroy_session(sid)
    assert not ws.exists()


def test_cleanup_expired_removes_old_sessions(session_manager):
    sid = session_manager.create_session(api_key="sk-test")
    session_manager._sessions[sid]["created_at"] = time.time() - 7200
    removed = session_manager.cleanup_expired(max_age_seconds=3600)
    assert removed >= 1
    assert sid not in session_manager._sessions


def test_get_loop_unknown_session_raises():
    manager = SessionManager()
    with pytest.raises(KeyError):
        manager.get_loop("nonexistent")