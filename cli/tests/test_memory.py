import json
import pytest
from pathlib import Path
from src.memory.store import MemoryStore
from src.memory.filter import filter_sensitive
from src.memory.retriever import MemoryRetriever


class TestMemoryStore:
    def test_creates_file(self, temp_harness_dir):
        store = MemoryStore(temp_harness_dir)
        data = store.load()
        assert data == store._default_data()

    def test_save_and_load(self, temp_harness_dir):
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

    def test_add_fix_record(self, temp_harness_dir):
        store = MemoryStore(temp_harness_dir)
        store.add_fix_record({"error_type": "AssertionError", "file": "calc.py", "strategy": "修复返回值"})
        data = store.load()
        assert len(data["fix_history"]) == 1
        assert data["fix_history"][0]["error_type"] == "AssertionError"

    def test_add_audit_entry(self, temp_harness_dir):
        store = MemoryStore(temp_harness_dir)
        store.add_audit_entry({"action": "tool_exec", "tool": "run_shell", "command": "pytest"})
        data = store.load()
        assert len(data["audit_log"]) == 1
        assert data["audit_log"][0]["tool"] == "run_shell"

    def test_clear(self, temp_harness_dir):
        store = MemoryStore(temp_harness_dir)
        store.save({"project": {"name": "test"}, "conventions": {}, "fix_history": [], "graylist_commands": [], "audit_log": []})
        store.clear()
        assert not store.memory_file.exists()


class TestFilter:
    def test_removes_api_key(self):
        assert "sk-abc123def4567890123456" not in filter_sensitive("my API key is sk-abc123def4567890123456")

    def test_removes_token(self):
        assert "ghp_1234567890abcdef" not in filter_sensitive("token=ghp_1234567890abcdef")

    def test_preserves_normal_text(self):
        assert filter_sensitive("this is normal test output") == "this is normal test output"


class TestMemoryRetriever:
    def test_returns_empty_for_empty_memory(self, temp_harness_dir):
        store = MemoryStore(temp_harness_dir)
        retriever = MemoryRetriever(store)
        assert retriever.retrieve("fix the failing test", 500) == ""

    def test_includes_test_convention(self, temp_harness_dir):
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

    def test_matches_fix_history(self, temp_harness_dir):
        store = MemoryStore(temp_harness_dir)
        store.add_fix_record({"error_type": "AssertionError", "file": "calc.py", "strategy": "修复返回值逻辑"})
        retriever = MemoryRetriever(store)
        result = retriever.retrieve("fix assertion error in test", 500)
        assert "AssertionError" in result
        assert "calc.py" in result

    def test_respects_max_chars(self, temp_harness_dir):
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