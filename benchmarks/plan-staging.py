#!/usr/bin/env python3
"""Create a read-only staging recommendation from a benchmark plan.

The planner selects a small model set that covers the requested benchmark
capabilities while preferring models that are already local and then smaller
cold models. It never copies, deletes, registers, loads, or downloads models.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def complete_location(candidate: dict) -> dict | None:
    for loc in candidate.get("locations", []):
        if loc.get("complete") is True:
            return loc
    return None


def score(candidate: dict, uncovered: set[str]) -> tuple:
    caps = set(candidate.get("capabilities", []))
    new_coverage = len(caps & uncovered)
    state = candidate.get("plan_state")
    local_bonus = 2 if state == "local_now" else 1 if state == "needs_staging" else 0
    size = candidate.get("declared_size_gb")
    size = float(size) if isinstance(size, (int, float)) else 10_000.0
    # Sort descending for first two fields, ascending for size via negative size.
    return (new_coverage, local_bonus, -size)


def select_minimal(candidates: list[dict], required: set[str]) -> list[dict]:
    usable = [
        c for c in candidates
        if c.get("plan_state") in {"local_now", "needs_staging"}
        and set(c.get("capabilities", [])) & required
    ]
    uncovered = set(required)
    chosen: list[dict] = []

    while uncovered:
        ranked = sorted(usable, key=lambda c: score(c, uncovered), reverse=True)
        if not ranked or len(set(ranked[0].get("capabilities", [])) & uncovered) == 0:
            break
        best = ranked[0]
        chosen.append(best)
        uncovered -= set(best.get("capabilities", []))
        usable = [c for c in usable if c.get("model") != best.get("model")]

    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-plan", required=True)
    ap.add_argument("--phase", default="phase_1_small_specialists")
    ap.add_argument("--output-dir", default="artifacts/staging-plans")
    args = ap.parse_args()

    plan = load_json(args.benchmark_plan)
    phase = next((p for p in plan.get("phases", []) if p.get("id") == args.phase), None)
    if phase is None:
        raise SystemExit(f"phase not found: {args.phase}")

    candidates = phase.get("candidates", [])
    required = set()
    for c in candidates:
        required.update(c.get("capabilities", []))

    chosen = select_minimal(candidates, required)
    covered = set()
    items = []
    total_stage_gb = 0.0

    for c in chosen:
        caps = sorted(set(c.get("capabilities", [])) & required)
        covered.update(caps)
        state = c.get("plan_state")
        size = c.get("declared_size_gb")
        if state == "needs_staging" and isinstance(size, (int, float)):
            total_stage_gb += float(size)
        items.append({
            "model": c.get("model"),
            "plan_state": state,
            "capabilities": caps,
            "declared_size_gb": size,
            "preferred_source": complete_location(c),
            "action": "none" if state == "local_now" else "stage_to_local_ssd",
        })

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "schema_version": 1,
        "captured_at_utc": stamp,
        "policy": {
            "read_only": True,
            "automatic_copy": False,
            "automatic_eviction": False,
            "automatic_registration": False,
            "automatic_download": False,
        },
        "input_plan": args.benchmark_plan,
        "phase": args.phase,
        "required_capabilities": sorted(required),
        "covered_capabilities": sorted(covered),
        "uncovered_capabilities": sorted(required - covered),
        "summary": {
            "selected_models": len(items),
            "models_already_local": sum(1 for x in items if x["plan_state"] == "local_now"),
            "models_to_stage": sum(1 for x in items if x["plan_state"] == "needs_staging"),
            "declared_stage_size_gb": round(total_stage_gb, 3),
        },
        "selection_policy": "greedy capability coverage; prefer local_now, then smaller staged size",
        "items": items,
    }

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"staging-plan-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
