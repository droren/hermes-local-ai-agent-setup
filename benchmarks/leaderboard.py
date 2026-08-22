#!/usr/bin/env python3
"""Build a compact leaderboard from an evaluation JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

GRADE_RANK = {"pass": 2, "conditional": 1, "fail": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("evaluation")
    ap.add_argument("--capability")
    args = ap.parse_args()

    payload = json.loads(Path(args.evaluation).read_text(encoding="utf-8"))
    rows = payload.get("results", [])
    if args.capability:
        rows = [r for r in rows if r.get("capability") == args.capability]

    rows.sort(
        key=lambda r: (
            -GRADE_RANK.get(r.get("grade"), -1),
            -float(r.get("score") or 0),
            float(r.get("wall_seconds") or 10**9),
            -float(r.get("tokens_per_second") or 0),
        )
    )

    print(f"{'MODEL':24} {'CAPABILITY':22} {'SCORE':>6} {'GRADE':>11} {'WALL(s)':>9} {'TOK/s':>9} {'OUT':>6}")
    print("-" * 94)
    for r in rows:
        tps = r.get("tokens_per_second")
        print(
            f"{str(r.get('model') or '')[:24]:24} "
            f"{str(r.get('capability') or '')[:22]:22} "
            f"{float(r.get('score') or 0):6.1f} "
            f"{str(r.get('grade') or ''):>11} "
            f"{float(r.get('wall_seconds') or 0):9.3f} "
            f"{(f'{float(tps):.1f}' if tps is not None else '-'):>9} "
            f"{int(r.get('output_tokens') or 0):6d}"
        )


if __name__ == "__main__":
    main()
