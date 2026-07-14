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
                    parts.append(f"- {r.get('error_type')} @ {r.get('file')}: {r.get('strategy')}")

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