#!/usr/bin/env python3
"""Run multiple independent fixtures per capability for local worker candidates."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CASES = [
    ('code.review', 'benchmarks/prompts/code-review-small.md'),
    ('code.review', 'benchmarks/prompts/code-review-boundary-2.md'),
    ('code.review', 'benchmarks/prompts/code-review-logic-3.md'),
    ('test.design', 'benchmarks/prompts/test-design-small.md'),
    ('test.design', 'benchmarks/prompts/test-design-range-2.md'),
    ('test.design', 'benchmarks/prompts/test-design-branch-3.md'),
    ('code.implement.small', 'benchmarks/prompts/code-implement-small.md'),
    ('code.implement.small', 'benchmarks/prompts/code-implement-range-2.md'),
    ('code.implement.small', 'benchmarks/prompts/code-implement-branch-3.md'),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', action='append', required=True)
    ap.add_argument('--endpoint', default='http://127.0.0.1:11434')
    ap.add_argument('--context', type=int, default=8192)
    ap.add_argument('--max-output-tokens', type=int, default=384)
    ap.add_argument('--timeout', type=int, default=120)
    ap.add_argument('--output-dir', default='artifacts/benchmarks/robustness-v1')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    runner = root / 'benchmarks' / 'benchmark-model.py'
    failures = 0

    for model in args.model:
        for capability, rel_prompt in CASES:
            prompt = root / rel_prompt
            print('RUN', model, capability, prompt.name)
            cmd = [
                sys.executable, str(runner),
                '--model', model,
                '--capability', capability,
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
