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
    "llm": {
        "model": "glm-5.2",
        "base_url": "https://njusehub.info/v1",
        "timeout": 30,
        "max_retries": 3,
    },
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