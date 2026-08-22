#!/usr/bin/env python3
"""Run one capability fixture across multiple explicitly named local Ollama models."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROMPTS = {
    'routing.classify': 'benchmarks/prompts/routing-classify.md',
    'structured_output': 'benchmarks/prompts/structured-output.md',
    'summarization.compact': 'benchmarks/prompts/summarization-compact.md',
    'code.review': 'benchmarks/prompts/code-review-small.md',
    'test.design': 'benchmarks/prompts/test-design-small.md',
    'code.implement.small': 'benchmarks/prompts/code-implement-small.md',
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--capability', required=True, choices=sorted(PROMPTS))
    ap.add_argument('--model', action='append', required=True)
    ap.add_argument('--endpoint', default='http://127.0.0.1:11434')
    ap.add_argument('--context', type=int, default=8192)
    ap.add_argument('--max-output-tokens', type=int, default=384)
    ap.add_argument('--timeout', type=int, default=120)
    ap.add_argument('--output-dir', default='artifacts/benchmarks/compare')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    runner = root / 'benchmarks' / 'benchmark-model.py'
    prompt = root / PROMPTS[args.capability]
    failures = 0
    for model in args.model:
        print('RUN', model, args.capability)
        cmd = [
            sys.executable, str(runner),
            '--model', model,
            '--capability', args.capability,
            '--prompt-file', str(prompt),
            '--endpoint', args.endpoint,
            '--context', str(args.context),
            '--max-output-tokens', str(args.max_output_tokens),
            '--timeout', str(args.timeout),
            '--output-dir', args.output_dir,
        ]
        result = subprocess.run(cmd, cwd=root)
        if result.returncode != 0:
            failures += 1
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
