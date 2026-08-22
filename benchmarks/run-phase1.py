#!/usr/bin/env python3
"""Run the initial Phase 1 capability benchmarks for the staged local models.

This runner intentionally keeps scope small:
- qwen3:1.7b -> routing.classify, structured_output proxy, summarization.compact proxy
- granite-code:8b -> code.review plus initial code/test fixtures as they are added

It shells out to benchmark-model.py so all metrics stay in one result schema.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CASES = [
    {
        "model": "qwen3:1.7b",
        "capability": "routing.classify",
        "prompt": "benchmarks/prompts/routing-classify.md",
    },
    {
        "model": "qwen3:1.7b",
        "capability": "structured_output",
        "prompt": "benchmarks/prompts/routing-classify.md",
    },
    {
        "model": "qwen3:1.7b",
        "capability": "summarization.compact",
        "prompt": "benchmarks/prompts/summarization-compact.md",
    },
    {
        "model": "granite-code:8b",
        "capability": "code.review",
        "prompt": "benchmarks/prompts/code-review-small.md",
    },
    {
        "model": "granite-code:8b",
        "capability": "test.design",
        "prompt": "benchmarks/prompts/test-design-small.md",
    },
    {
        "model": "granite-code:8b",
        "capability": "code.implement.small",
        "prompt": "benchmarks/prompts/code-implement-small.md",
    },
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434")
    ap.add_argument("--context", type=int, default=8192)
    ap.add_argument("--output-dir", default="artifacts/benchmarks/phase1")
    ap.add_argument("--model", action="append", help="Restrict to one or more model names")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    runner = root / "benchmarks" / "benchmark-model.py"
    selected = set(args.model or [])

    failures = 0
    for case in CASES:
        if selected and case["model"] not in selected:
            continue
        prompt = root / case["prompt"]
        if not prompt.exists():
            print(f"SKIP missing fixture: {case['prompt']}")
            failures += 1
            continue

        cmd = [
            sys.executable,
            str(runner),
            "--model", case["model"],
            "--capability", case["capability"],
            "--prompt-file", str(prompt),
            "--endpoint", args.endpoint,
            "--context", str(args.context),
            "--output-dir", args.output_dir,
        ]
        print("RUN", case["model"], case["capability"])
        result = subprocess.run(cmd, cwd=root)
        if result.returncode != 0:
            failures += 1

    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
