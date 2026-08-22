#!/usr/bin/env python3
"""Measure sequential vs concurrent execution for the initial two-model local agent team.

Concurrency is only considered useful when both jobs complete with usable output.
The router and worker therefore have separate output-token budgets and lightweight
quality checks in addition to timing/throughput measurements.
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
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
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


def quality_check(role: str, text: str, done_reason: str | None) -> dict:
    if done_reason != 'stop':
        return {'usable': False, 'reason': f'done_reason={done_reason}'}

    if role == 'router':
        obj = extract_json(text)
        required = {'capability', 'complexity', 'needs_decomposition', 'reason'}
        if not isinstance(obj, dict):
            return {'usable': False, 'reason': 'router response is not valid JSON'}
        if not required.issubset(obj):
            return {'usable': False, 'reason': 'router JSON missing required keys'}
        return {'usable': True, 'reason': 'valid routing JSON'}

    if role == 'worker':
        low = (text or '').lower()
        required = ['def normalize_discount', 'discount < 0', 'discount > 100', 'raise valueerror', 'return discount']
        missing = [x for x in required if x not in low]
        if missing:
            return {'usable': False, 'reason': f'worker response missing expected implementation markers: {missing}'}
        return {'usable': True, 'reason': 'expected implementation markers present'}

    return {'usable': bool(text), 'reason': 'nonempty output' if text else 'empty output'}


def run_one(endpoint: str, role: str, model: str, prompt: str, context: int, max_tokens: int) -> dict:
    started = time.perf_counter()
    response = post_json(
        endpoint.rstrip('/') + '/api/generate',
        {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'keep_alive': '10m',
            'options': {
                'num_ctx': context,
                'num_predict': max_tokens,
                'temperature': 0,
            },
        },
    )
    wall = time.perf_counter() - started
    eval_count = int(response.get('eval_count', 0) or 0)
    eval_ns = int(response.get('eval_duration', 0) or 0)
    tps = eval_count / (eval_ns / 1e9) if eval_ns else None
    text = response.get('response', '') or ''
    done_reason = response.get('done_reason')
    quality = quality_check(role, text, done_reason)
    return {
        'role': role,
        'model': model,
        'wall_seconds': round(wall, 3),
        'output_tokens': eval_count,
        'tokens_per_second': round(tps, 3) if tps is not None else None,
        'done_reason': done_reason,
        'quality': quality,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default='http://127.0.0.1:11434')
    ap.add_argument('--router-model', default='qwen3:1.7b')
    ap.add_argument('--worker-model', default='granite3.3:2b')
    ap.add_argument('--context', type=int, default=8192)
    ap.add_argument('--router-max-output-tokens', type=int, default=384)
    ap.add_argument('--worker-max-output-tokens', type=int, default=192)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--output-dir', default='artifacts/benchmarks/concurrency')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    router_prompt = (root / 'benchmarks/prompts/routing-classify.md').read_text(encoding='utf-8')
    worker_prompt = (root / 'benchmarks/prompts/code-implement-small.md').read_text(encoding='utf-8')

    # Warm both models and keep them resident when memory allows.
    run_one(args.endpoint, 'warmup', args.router_model, 'Reply with OK.', args.context, 8)
    run_one(args.endpoint, 'warmup', args.worker_model, 'Reply with OK.', args.context, 8)

    runs = []
    for index in range(1, args.runs + 1):
        seq_started = time.perf_counter()
        seq_router = run_one(args.endpoint, 'router', args.router_model, router_prompt, args.context, args.router_max_output_tokens)
        seq_worker = run_one(args.endpoint, 'worker', args.worker_model, worker_prompt, args.context, args.worker_max_output_tokens)
        seq_total = time.perf_counter() - seq_started

        conc_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_router = pool.submit(run_one, args.endpoint, 'router', args.router_model, router_prompt, args.context, args.router_max_output_tokens)
            f_worker = pool.submit(run_one, args.endpoint, 'worker', args.worker_model, worker_prompt, args.context, args.worker_max_output_tokens)
            conc_router = f_router.result()
            conc_worker = f_worker.result()
        conc_total = time.perf_counter() - conc_started

        sequential_usable = bool(seq_router['quality']['usable'] and seq_worker['quality']['usable'])
        concurrent_usable = bool(conc_router['quality']['usable'] and conc_worker['quality']['usable'])

        runs.append({
            'run': index,
            'sequential': {
                'total_wall_seconds': round(seq_total, 3),
                'usable': sequential_usable,
                'router': seq_router,
                'worker': seq_worker,
            },
            'concurrent': {
                'total_wall_seconds': round(conc_total, 3),
                'usable': concurrent_usable,
                'router': conc_router,
                'worker': conc_worker,
            },
        })
        print(
            f"run {index}: sequential={seq_total:.3f}s usable={sequential_usable} "
            f"concurrent={conc_total:.3f}s usable={concurrent_usable}"
        )

    usable_runs = [r for r in runs if r['sequential']['usable'] and r['concurrent']['usable']]
    seq_avg = sum(r['sequential']['total_wall_seconds'] for r in usable_runs) / len(usable_runs) if usable_runs else None
    conc_avg = sum(r['concurrent']['total_wall_seconds'] for r in usable_runs) / len(usable_runs) if usable_runs else None
    speedup = (seq_avg / conc_avg) if (seq_avg is not None and conc_avg) else None

    payload = {
        'schema_version': 2,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'models': {'router': args.router_model, 'worker': args.worker_model},
        'context': args.context,
        'token_budgets': {
            'router': args.router_max_output_tokens,
            'worker': args.worker_max_output_tokens,
        },
        'runs': runs,
        'summary': {
            'requested_runs': args.runs,
            'quality_valid_runs': len(usable_runs),
            'average_sequential_wall_seconds': round(seq_avg, 3) if seq_avg is not None else None,
            'average_concurrent_wall_seconds': round(conc_avg, 3) if conc_avg is not None else None,
            'effective_speedup': round(speedup, 3) if speedup is not None else None,
            'concurrency_validated': len(usable_runs) == args.runs,
        },
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = out_dir / f'concurrency-{stamp}.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
