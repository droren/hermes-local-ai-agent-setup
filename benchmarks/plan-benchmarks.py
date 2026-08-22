#!/usr/bin/env python3
"""Build a read-only benchmark execution plan from inventories and candidate matrix.

Inputs:
- cold model inventory JSON from inventory-model-library-v2.py
- optional host inventory JSON from inventory-host.sh
- candidate matrix YAML (minimal parser supports the current repository format)

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
    """Parse only the small YAML subset used by candidate-matrix-v0.2.yaml.

    Avoids adding PyYAML as a dependency. Supports:
      phases:
        - id: phase1
          candidates:
            - model: qwen3:1.7b
              capabilities: [routing.classify, summarization.compact]
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    phases: list[dict] = []
    phase: dict | None = None
    candidate: dict | None = None
    in_candidates = False

    def flush_candidate() -> None:
        nonlocal candidate, phase
        if candidate is not None and phase is not None:
            phase.setdefault("candidates", []).append(candidate)
            candidate = None

    def flush_phase() -> None:
        nonlocal phase
        flush_candidate()
        if phase is not None:
            phases.append(phase)
            phase = None

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))

        if stripped.startswith("- id:") and indent <= 2:
            flush_phase()
            phase = {"id": stripped.split(":", 1)[1].strip(), "candidates": []}
            in_candidates = False
            continue
        if phase is None:
            continue
        if stripped.startswith("description:"):
            phase["description"] = stripped.split(":", 1)[1].strip().strip('"')
            continue
        if stripped == "candidates:":
            in_candidates = True
            continue
        if in_candidates and stripped.startswith("- model:"):
            flush_candidate()
            candidate = {"model": stripped.split(":", 1)[1].strip()}
            continue
        if candidate is not None and stripped.startswith("capabilities:"):
            value = stripped.split(":", 1)[1].strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                candidate["capabilities"] = [x.strip() for x in inner.split(",") if x.strip()]
            else:
                candidate["capabilities"] = []
            continue
        if candidate is not None and stripped.startswith("notes:"):
            candidate["notes"] = stripped.split(":", 1)[1].strip().strip('"')
            continue

    flush_phase()
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
                "plan_state": state,
                "declared_size_gb": (record or {}).get("declared_size_gb"),
                "cold_state": (record or {}).get("state"),
                "locations": (record or {}).get("locations", []),
                "notes": cand.get("notes"),
            }
            planned["candidates"].append(entry)
        planned_phases.append(planned)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "schema_version": 1,
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
