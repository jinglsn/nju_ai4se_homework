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