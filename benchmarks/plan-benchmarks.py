#!/usr/bin/env python3
"""Build a read-only benchmark execution plan from inventories and candidate matrix.

Inputs:
- cold model inventory JSON from inventory-model-library-v2.py
- optional host inventory JSON from inventory-host.sh
- candidate matrix YAML using capabilities + benchmark_order

Output:
- JSON plan classifying candidates as local_now, needs_staging, unavailable, or external_reference

This script does not copy, delete, register, load, benchmark, or download models.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_candidate_matrix(path: str) -> list[dict]:
    """Parse the repository's dependency-light YAML subset.

    Expected structure:

      capabilities:
        routing.classify:
          priority: high
          candidates:
            - qwen3:1.7b

      benchmark_order:
        phase_1_small_specialists:
          - qwen3:1.7b

    The parser deliberately avoids PyYAML. It extracts capability membership and
    benchmark phase ordering, then emits the normalized phase/candidate shape
    consumed by the planner.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    capability_to_models: dict[str, list[str]] = {}
    capability_priority: dict[str, str] = {}
    benchmark_order: dict[str, list[str]] = {}

    section: str | None = None
    current_capability: str | None = None
    in_capability_candidates = False
    current_phase: str | None = None

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))

        if indent == 0 and stripped == "capabilities:":
            section = "capabilities"
            current_capability = None
            current_phase = None
            continue

        if indent == 0 and stripped == "benchmark_order:":
            section = "benchmark_order"
            current_capability = None
            current_phase = None
            continue

        if indent == 0 and stripped.endswith(":"):
            # Any other top-level section ends parsing of the current structured block.
            section = None
            current_capability = None
            current_phase = None
            continue

        if section == "capabilities":
            if indent == 2 and stripped.endswith(":"):
                current_capability = stripped[:-1].strip()
                capability_to_models.setdefault(current_capability, [])
                in_capability_candidates = False
                continue

            if current_capability is None:
                continue

            if indent == 4 and stripped.startswith("priority:"):
                capability_priority[current_capability] = stripped.split(":", 1)[1].strip()
                continue

            if indent == 4 and stripped == "candidates:":
                in_capability_candidates = True
                continue

            if indent == 6 and in_capability_candidates and stripped.startswith("- "):
                model = stripped[2:].strip()
                if model:
                    capability_to_models[current_capability].append(model)
                continue

        if section == "benchmark_order":
            if indent == 2 and stripped.endswith(":"):
                current_phase = stripped[:-1].strip()
                benchmark_order.setdefault(current_phase, [])
                continue

            if indent == 4 and current_phase and stripped.startswith("- "):
                model = stripped[2:].strip()
                if model:
                    benchmark_order[current_phase].append(model)
                continue

    model_capabilities: dict[str, list[str]] = {}
    model_priorities: dict[str, list[str]] = {}
    for capability, models in capability_to_models.items():
        for model in models:
            model_capabilities.setdefault(model, []).append(capability)
            priority = capability_priority.get(capability)
            if priority:
                model_priorities.setdefault(model, []).append(priority)

    phases: list[dict] = []
    for phase_id, models in benchmark_order.items():
        candidates = []
        for model in models:
            candidates.append({
                "model": model,
                "capabilities": sorted(model_capabilities.get(model, [])),
                "capability_priorities": sorted(set(model_priorities.get(model, []))),
            })
        phases.append({
            "id": phase_id,
            "description": phase_id.replace("_", " "),
            "candidates": candidates,
        })

    return phases


def active_model_names(host: dict) -> set[str]:
    models = (
        host.get("runtime", {})
        .get("ollama", {})
        .get("models", [])
    )
    return {str(m.get("name", "")) for m in models if m.get("name")}


def build_index(cold: dict) -> dict[str, dict]:
    return {m.get("name"): m for m in cold.get("models", []) if m.get("name")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cold-inventory", required=True)
    ap.add_argument("--host-inventory")
    ap.add_argument("--matrix", default="benchmarks/candidate-matrix-v0.2.yaml")
    ap.add_argument("--output-dir", default="artifacts/benchmark-plans")
    args = ap.parse_args()

    cold = load_json(args.cold_inventory)
    host = load_json(args.host_inventory)
    phases = parse_candidate_matrix(args.matrix)
    cold_index = build_index(cold)
    active = active_model_names(host)

    planned_phases: list[dict] = []
    counts = {"local_now": 0, "needs_staging": 0, "unavailable": 0, "external_reference": 0}

    for phase in phases:
        planned = {"id": phase.get("id"), "description": phase.get("description"), "candidates": []}
        for cand in phase.get("candidates", []):
            name = cand["model"]
            record = cold_index.get(name)
            if name in active:
                state = "local_now"
            elif record and record.get("state") == "cold_available":
                state = "needs_staging"
            elif record and record.get("state") == "external_reference":
                state = "external_reference"
            else:
                state = "unavailable"

            counts[state] += 1
            entry = {
                "model": name,
                "capabilities": cand.get("capabilities", []),
                "capability_priorities": cand.get("capability_priorities", []),
                "plan_state": state,
                "declared_size_gb": (record or {}).get("declared_size_gb"),
                "cold_state": (record or {}).get("state"),
                "locations": (record or {}).get("locations", []),
            }
            planned["candidates"].append(entry)
        planned_phases.append(planned)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "schema_version": 2,
        "captured_at_utc": stamp,
        "policy": {
            "read_only": True,
            "automatic_staging": False,
            "automatic_eviction": False,
            "automatic_download": False,
        },
        "inputs": {
            "cold_inventory": args.cold_inventory,
            "host_inventory": args.host_inventory,
            "matrix": args.matrix,
        },
        "summary": counts,
        "phases": planned_phases,
    }

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"benchmark-plan-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
