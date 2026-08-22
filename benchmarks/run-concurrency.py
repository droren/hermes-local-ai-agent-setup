#!/usr/bin/env python3
"""Measure sequential vs concurrent execution for the initial two-model local agent team."""
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


def run_one(endpoint: str, model: str, prompt: str, context: int, max_tokens: int) -> dict:
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
    return {
        'model': model,
        'wall_seconds': round(wall, 3),
        'output_tokens': eval_count,
        'tokens_per_second': round(tps, 3) if tps is not None else None,
        'done_reason': response.get('done_reason'),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default='http://127.0.0.1:11434')
    ap.add_argument('--router-model', default='qwen3:1.7b')
    ap.add_argument('--worker-model', default='granite3.3:2b')
    ap.add_argument('--context', type=int, default=8192)
    ap.add_argument('--max-output-tokens', type=int, default=256)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--output-dir', default='artifacts/benchmarks/concurrency')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    router_prompt = (root / 'benchmarks/prompts/routing-classify.md').read_text(encoding='utf-8')
    worker_prompt = (root / 'benchmarks/prompts/code-implement-small.md').read_text(encoding='utf-8')

    # Warm both models and keep them resident when memory allows.
    run_one(args.endpoint, args.router_model, 'Reply with OK.', args.context, 8)
    run_one(args.endpoint, args.worker_model, 'Reply with OK.', args.context, 8)

    runs = []
    for index in range(1, args.runs + 1):
        seq_started = time.perf_counter()
        seq_router = run_one(args.endpoint, args.router_model, router_prompt, args.context, args.max_output_tokens)
        seq_worker = run_one(args.endpoint, args.worker_model, worker_prompt, args.context, args.max_output_tokens)
        seq_total = time.perf_counter() - seq_started

        conc_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_router = pool.submit(run_one, args.endpoint, args.router_model, router_prompt, args.context, args.max_output_tokens)
            f_worker = pool.submit(run_one, args.endpoint, args.worker_model, worker_prompt, args.context, args.max_output_tokens)
            conc_router = f_router.result()
            conc_worker = f_worker.result()
        conc_total = time.perf_counter() - conc_started

        runs.append({
            'run': index,
            'sequential': {
                'total_wall_seconds': round(seq_total, 3),
                'router': seq_router,
                'worker': seq_worker,
            },
            'concurrent': {
                'total_wall_seconds': round(conc_total, 3),
                'router': conc_router,
                'worker': conc_worker,
            },
        })
        print(f"run {index}: sequential={seq_total:.3f}s concurrent={conc_total:.3f}s")

    seq_avg = sum(r['sequential']['total_wall_seconds'] for r in runs) / len(runs)
    conc_avg = sum(r['concurrent']['total_wall_seconds'] for r in runs) / len(runs)
    speedup = seq_avg / conc_avg if conc_avg else None

    payload = {
        'schema_version': 1,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'models': {'router': args.router_model, 'worker': args.worker_model},
        'context': args.context,
        'max_output_tokens': args.max_output_tokens,
        'runs': runs,
        'summary': {
            'average_sequential_wall_seconds': round(seq_avg, 3),
            'average_concurrent_wall_seconds': round(conc_avg, 3),
            'effective_speedup': round(speedup, 3) if speedup is not None else None,
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
