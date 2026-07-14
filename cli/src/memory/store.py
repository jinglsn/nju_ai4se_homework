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