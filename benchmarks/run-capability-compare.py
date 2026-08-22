#!/usr/bin/env python3
"""Run one capability fixture across multiple explicitly named local Ollama models.

The runner performs a local Ollama preflight first. Models that are not registered
locally are reported as NOT_LOCAL and are never sent to benchmark-model.py. This
prevents storage-state failures from being misclassified as capability failures.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

PROMPTS = {
    'routing.classify': 'benchmarks/prompts/routing-classify.md',
    'structured_output': 'benchmarks/prompts/structured-output.md',
    'summarization.compact': 'benchmarks/prompts/summarization-compact.md',
    'code.review': 'benchmarks/prompts/code-review-small.md',
    'test.design': 'benchmarks/prompts/test-design-small.md',
    'code.implement.small': 'benchmarks/prompts/code-implement-small.md',
}


def local_models(endpoint: str, timeout: int = 10) -> set[str]:
    url = endpoint.rstrip('/') + '/api/tags'
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return {str(m.get('name', '')) for m in payload.get('models', []) if m.get('name')}


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

    try:
        available = local_models(args.endpoint)
    except Exception as exc:
        raise SystemExit(f'Unable to query local Ollama models at {args.endpoint}: {exc}')

    missing = [model for model in args.model if model not in available]
    runnable = [model for model in args.model if model in available]

    for model in missing:
        print('NOT_LOCAL', model, '- stage/register this model before benchmarking')

    if not runnable:
        raise SystemExit('No requested models are registered locally; benchmark not started.')

    failures = 0
    for model in runnable:
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

    if missing:
        print(f'SKIPPED {len(missing)} non-local model(s); these are not capability failures.')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
