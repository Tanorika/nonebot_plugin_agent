"""Build/resume a model-backed tree without starting the bot or rewriting chat logs."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import threading

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def settings():
    # Read literal defaults without importing config.py (its default_factory
    # scans sticker files). Respect the same bot .env / environment overrides.
    values = {}
    config = ast.parse((ROOT / "config.py").read_text(encoding="utf-8"))
    cls = next(node for node in config.body if isinstance(node, ast.ClassDef) and node.name == "Config")
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = node.value
            if isinstance(value, ast.Call):
                value = next((keyword.value for keyword in value.keywords
                              if keyword.arg == "default"), None)
            try:
                values[node.target.id] = ast.literal_eval(value)
            except (ValueError, TypeError):
                continue
    bot_root = ROOT.parents[2]
    overrides = {key.casefold(): value for key, value in dotenv_values(bot_root / ".env").items()
                 if value is not None}
    environment = os.environ.get("ENVIRONMENT", overrides.get("environment", "prod"))
    overrides.update({key.casefold(): value for key, value in
                      dotenv_values(bot_root / f".env.{environment}").items() if value is not None})
    overrides.update({key.casefold(): value for key, value in os.environ.items()})
    for key in values:
        if key in overrides:
            values[key] = overrides[key]
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--fanout", type=int)
    parser.add_argument("--summary-chars", type=int)
    parser.add_argument("--max-nodes", type=int, help="Limit this pass; completed summaries are retained")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent offline requests, 1..8")
    parser.add_argument("--dry-run", action="store_true", help="Build topology and report progress without API calls")
    args = parser.parse_args()
    if not args.user_id.isdigit():
        parser.error("user-id must contain only digits")
    if args.max_nodes is not None and args.max_nodes < 1:
        parser.error("max-nodes must be positive")
    if not 1 <= args.workers <= 8:
        parser.error("workers must be 1..8")
    config = settings()
    fanout = args.fanout if args.fanout is not None else int(config["memory_tree_fanout"])
    chars = args.summary_chars if args.summary_chars is not None else int(config["memory_tree_summary_chars"])
    if not 2 <= fanout <= 16 or not 128 <= chars <= 2000:
        parser.error("fanout must be 2..16 and summary-chars must be 128..2000")
    source = ROOT / "memory" / f"{args.user_id}.json"
    history = json.loads(source.read_text(encoding="utf-8"))
    tree_module = load_module("offline_memory_tree", ROOT / "core/memory_tree.py")
    index = tree_module.tree_index_path(str(ROOT / "memory/trees"), args.user_id, fanout, chars)
    tree = tree_module.MemoryTree(str(index), history, fanout=fanout, summary_chars=chars)
    print(json.dumps(tree.stats()), flush=True)
    if args.dry_run:
        return
    api = load_module("offline_summary_api", ROOT / "core/llm_api.py")
    summary_module = load_module("offline_summary_model", ROOT / "core/memory_summarizer.py")
    client = api.LLMAPIClient(
        api_key=config["memory_tree_api_key"] or config["api_key"],
        base_url=config["memory_tree_base_url"] or config["base_url"],
        model=config["memory_tree_model"] or config["model"],
    )
    summarizer = summary_module.ModelSummarizer(client, timeout=int(config["memory_tree_timeout"]))
    done = 0
    claimed = 0
    progress_lock = threading.Lock()
    stopped = threading.Event()

    def work():
        nonlocal done, claimed
        while not stopped.is_set():
            with progress_lock:
                if args.max_nodes is not None and claimed >= args.max_nodes:
                    return
                claimed += 1
            try:
                count = tree.summarize_pending(summarizer, max_nodes=1)
            except Exception:
                stopped.set()
                raise
            if not count:
                return
            with progress_lock:
                done += count
                if done % 10 == 0:
                    print(json.dumps(tree.stats()), flush=True)

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(work) for _ in range(args.workers)]
            for future in futures:
                future.result()
    except Exception as error:
        print(f"Summary pass deferred: {type(error).__name__}: {error}; rerun to resume.", flush=True)
        print(json.dumps(tree.stats()), flush=True)
        raise SystemExit(1) from None
    print(json.dumps(tree.stats()), flush=True)


if __name__ == "__main__":
    main()
