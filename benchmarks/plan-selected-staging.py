#!/usr/bin/env python3
"""Create a read-only staging plan for explicitly selected benchmark models.

Use this when comparing a set of candidate models that were not chosen by the
greedy minimum Phase-1 staging planner.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--benchmark-plan', required=True)
    ap.add_argument('--model', action='append', required=True)
    ap.add_argument('--output-dir', default='artifacts/staging-plans')
    args = ap.parse_args()

    plan = json.loads(Path(args.benchmark_plan).read_text(encoding='utf-8'))
    index = {}
    for phase in plan.get('phases', []):
        for item in phase.get('candidates', []):
            if item.get('model'):
                index[item['model']] = item

    items = []
    total = 0.0
    missing = []
    for name in args.model:
        item = index.get(name)
        if not item:
            missing.append(name)
            continue
        if item.get('plan_state') == 'local_now':
            action = 'already_local'
            source = None
        elif item.get('plan_state') == 'needs_staging':
            complete = [x for x in item.get('locations', []) if x.get('complete')]
            source = complete[0] if complete else None
            action = 'stage_to_local_ssd' if source else 'blocked_no_complete_source'
        else:
            source = None
            action = 'blocked_' + str(item.get('plan_state'))

        size = float(item.get('declared_size_gb') or 0)
        if action == 'stage_to_local_ssd':
            total += size
        items.append({
            'model': name,
            'plan_state': item.get('plan_state'),
            'capabilities': item.get('capabilities', []),
            'declared_size_gb': size,
            'preferred_source': source,
            'action': action,
        })

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload = {
        'schema_version': 1,
        'captured_at_utc': stamp,
        'policy': {
            'read_only': True,
            'automatic_copy': False,
            'automatic_eviction': False,
            'automatic_registration': False,
            'automatic_download': False,
        },
        'input_plan': args.benchmark_plan,
        'requested_models': args.model,
        'missing_from_benchmark_plan': missing,
        'summary': {
            'requested_models': len(args.model),
            'resolved_models': len(items),
            'models_to_stage': sum(1 for x in items if x['action'] == 'stage_to_local_ssd'),
            'declared_stage_size_gb': round(total, 3),
        },
        'items': items,
    }

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f'selected-staging-plan-{stamp}.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
