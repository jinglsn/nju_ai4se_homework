import json
import pytest
from pathlib import Path
from src.config.loader import load_config, DEFAULT_CONFIG, merge_configs


class TestConfigLoader:
    def test_default_config_has_required_keys(self):
        assert DEFAULT_CONFIG["max_iterations"] == 10
        assert DEFAULT_CONFIG["timeout"] == 120
        assert DEFAULT_CONFIG["llm"]["model"] == "glm-5.2"

    def test_merge_configs_project_overrides_global(self):
        global_cfg = {"max_iterations": 10, "timeout": 120}
        project_cfg = {"max_iterations": 5}
        merged = merge_configs(global_cfg, project_cfg)
        assert merged["max_iterations"] == 5
        assert merged["timeout"] == 120

    def test_merge_configs_nested_dict(self):
        global_cfg = {"tools": {"read_file": True, "run_shell": True}}
        project_cfg = {"tools": {"run_shell": False}}
        merged = merge_configs(global_cfg, project_cfg)
        assert merged["tools"]["read_file"] is True
        assert merged["tools"]["run_shell"] is False

    def test_load_config_without_project_file(self, temp_harness_dir):
        project_root = temp_harness_dir.parent
        config = load_config(project_root)
        assert config["max_iterations"] == 10

    def test_load_config_with_project_file(self, temp_harness_dir):
        project_root = temp_harness_dir.parent
        project_config = {"max_iterations": 3, "timeout": 60}
        with open(temp_harness_dir / "config.json", "w") as f:
            json.dump(project_config, f)
        config = load_config(project_root, global_config_path=None)
        assert config["max_iterations"] == 3
        assert config["timeout"] == 60