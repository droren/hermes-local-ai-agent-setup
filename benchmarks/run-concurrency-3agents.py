#!/usr/bin/env python3
"""Measure sequential vs concurrent execution for the first three-role local agent team.

Roles:
- router: qwen3:1.7b using routing.classify
- worker: granite3.3:2b using code.implement.small
- tester: ministral-3:3b using test.design

The benchmark validates that all three responses remain usable while measuring end-to-end wall time.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


def post_json(url: str, payload: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def extract_json(text: str):
    s = (text or '').strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find('{')
    end = s.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            return None
    return None


def validate(role: str, text: str, done_reason: str | None) -> tuple[bool, str]:
    if done_reason == 'length':
        return False, 'hit_output_limit'
    if role == 'router':
        obj = extract_json(text)
        ok = isinstance(obj, dict) and obj.get('capability') and obj.get('complexity') and isinstance(obj.get('needs_decomposition'), bool)
        return ok, 'valid_router_json' if ok else 'invalid_router_output'
    if role == 'worker':
        low = text.lower()
        ok = 'def normalize_discount' in low and 'raise valueerror' in low and 'return discount' in low
        return ok, 'valid_implementation' if ok else 'invalid_implementation'
    if role == 'tester':
        obj = extract_json(text)
        if not isinstance(obj, dict) or not isinstance(obj.get('tests'), list):
            return False, 'invalid_test_json'
        joined = json.dumps(obj.get('tests')).lower()
        ok = all(token in joined for token in ['-1', '0', '100', '101'])
        return ok, 'valid_boundary_tests' if ok else 'missing_boundary_tests'
    return False, 'unknown_role'


def run_one(endpoint: str, role: str, model: str, prompt: str, context: int, max_tokens: int) -> dict:
    started = time.perf_counter()
    response = post_json(
        endpoint.rstrip('/') + '/api/generate',
        {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'keep_alive': '10m',
            'options': {'num_ctx': context, 'num_predict': max_tokens, 'temperature': 0},
        },
    )
    wall = time.perf_counter() - started
    eval_count = int(response.get('eval_count', 0) or 0)
    eval_ns = int(response.get('eval_duration', 0) or 0)
    tps = eval_count / (eval_ns / 1e9) if eval_ns else None
    text = response.get('response', '') or ''
    usable, validation = validate(role, text, response.get('done_reason'))
    return {
        'role': role,
        'model': model,
        'wall_seconds': round(wall, 3),
        'output_tokens': eval_count,
        'tokens_per_second': round(tps, 3) if tps is not None else None,
        'done_reason': response.get('done_reason'),
        'usable': usable,
        'validation': validation,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default='http://127.0.0.1:11434')
    ap.add_argument('--router-model', default='qwen3:1.7b')
    ap.add_argument('--worker-model', default='granite3.3:2b')
    ap.add_argument('--tester-model', default='ministral-3:3b')
    ap.add_argument('--context', type=int, default=8192)
    ap.add_argument('--router-max-output-tokens', type=int, default=384)
    ap.add_argument('--worker-max-output-tokens', type=int, default=192)
    ap.add_argument('--tester-max-output-tokens', type=int, default=384)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--output-dir', default='artifacts/benchmarks/concurrency-3agents')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    prompts = {
        'router': (root / 'benchmarks/prompts/routing-classify.md').read_text(encoding='utf-8'),
        'worker': (root / 'benchmarks/prompts/code-implement-small.md').read_text(encoding='utf-8'),
        'tester': (root / 'benchmarks/prompts/test-design-small.md').read_text(encoding='utf-8'),
    }
    models = {'router': args.router_model, 'worker': args.worker_model, 'tester': args.tester_model}
    budgets = {'router': args.router_max_output_tokens, 'worker': args.worker_max_output_tokens, 'tester': args.tester_max_output_tokens}

    for role in ('router', 'worker', 'tester'):
        run_one(args.endpoint, role, models[role], 'Reply with OK.', args.context, 8)

    runs = []
    for index in range(1, args.runs + 1):
        seq_started = time.perf_counter()
        seq = {}
        for role in ('router', 'worker', 'tester'):
            seq[role] = run_one(args.endpoint, role, models[role], prompts[role], args.context, budgets[role])
        seq_total = time.perf_counter() - seq_started
        seq_usable = all(x['usable'] for x in seq.values())

        conc_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                role: pool.submit(run_one, args.endpoint, role, models[role], prompts[role], args.context, budgets[role])
                for role in ('router', 'worker', 'tester')
            }
            conc = {role: futures[role].result() for role in ('router', 'worker', 'tester')}
        conc_total = time.perf_counter() - conc_started
        conc_usable = all(x['usable'] for x in conc.values())

        print(f"run {index}: sequential={seq_total:.3f}s usable={seq_usable} concurrent={conc_total:.3f}s usable={conc_usable}")
        runs.append({
            'run': index,
            'sequential': {'total_wall_seconds': round(seq_total, 3), 'usable': seq_usable, **seq},
            'concurrent': {'total_wall_seconds': round(conc_total, 3), 'usable': conc_usable, **conc},
        })

    valid = [r for r in runs if r['sequential']['usable'] and r['concurrent']['usable']]
    if valid:
        seq_avg = sum(r['sequential']['total_wall_seconds'] for r in valid) / len(valid)
        conc_avg = sum(r['concurrent']['total_wall_seconds'] for r in valid) / len(valid)
        speedup = seq_avg / conc_avg if conc_avg else None
    else:
        seq_avg = conc_avg = speedup = None

    payload = {
        'schema_version': 1,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'models': models,
        'context': args.context,
        'runs': runs,
        'summary': {
            'valid_runs': len(valid),
            'requested_runs': args.runs,
            'concurrency_validated': len(valid) == args.runs,
            'average_sequential_wall_seconds': round(seq_avg, 3) if seq_avg is not None else None,
            'average_concurrent_wall_seconds': round(conc_avg, 3) if conc_avg is not None else None,
            'effective_speedup': round(speedup, 3) if speedup is not None else None,
        },
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = out_dir / f'concurrency-3agents-{stamp}.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
