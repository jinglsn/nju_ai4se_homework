import argparse
import sys
import json
from pathlib import Path
from src.config.loader import load_config, DEFAULT_CONFIG
from src.config.keyring import set_api_key, key_status, clear_api_key
from src.memory.store import MemoryStore
from src.llm.real import RealLLM
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