#!/usr/bin/env python3
"""Hermes Next orchestrator v2 wrapper with deterministic decomposition fallback.

This intentionally reuses run_orchestrator.py while replacing only decomposition.
The wrapper exists while the prototype is evolving quickly; once validated, the
fallback will be folded into the main runner.
"""
from __future__ import annotations

import json
import re
from typing import Any

import run_orchestrator as base


def heuristic_decompose(task: str, route: dict[str, Any]) -> list[dict[str, Any]]:
    low = task.lower()
    parts: list[dict[str, Any]] = []

    def add(goal: str, acceptance: list[str]) -> None:
        parts.append({"id": f"task-{len(parts)+1}", "goal": goal, "acceptance": acceptance})

    if any(x in low for x in ("validation", "reject", "outside", "range")):
        add(
            "Implement the requested validation behavior without changing unrelated behavior.",
            ["invalid values are rejected", "valid boundary values remain accepted"],
        )
    if any(x in low for x in ("preserve", "without changing", "unchanged", "backward compat")):
        add(
            "Preserve the existing externally visible API behavior for valid inputs.",
            ["existing response shape/status for valid inputs is unchanged"],
        )
    if any(x in low for x in ("test", "tests", "boundary", "regression")):
        add(
            "Add or update automated tests covering the requested behavior.",
            ["lower boundary is tested", "upper boundary is tested", "values outside the range are tested"],
        )

    if not parts:
        clauses = [x.strip(" .") for x in re.split(r"\b(?:and|also|then)\b|;", task, flags=re.I) if x.strip(" .")]
        for clause in clauses[:4]:
            add(clause, ["subtask requirement is verifiably satisfied"])

    if len(parts) < 2 and route.get("complexity") in {"medium", "large"}:
        add("Verify the change against existing behavior and constraints.", ["no unintended regression is identified"])

    return parts[:6] or [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}]


def decompose_with_fallback(endpoint: str, model: str, task: str, route: dict[str, Any], ctx: int):
    if not route.get("needs_decomposition"):
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], None

    prompt = f"""You are a task decomposition classifier. Do not solve the task.
REQUEST: {task}
ROUTE: {json.dumps(route, ensure_ascii=False)}
Return one JSON object: {{"subtasks":[{{"id":"task-1","goal":"bounded goal","acceptance":["specific check"]}}]}}
Use 2-5 subtasks for medium/large work. Never return an empty object.
"""
    try:
        parsed, raw = base.generate_json_with_retry(
            endpoint,
            model,
            prompt,
            ctx=min(ctx, 4096),
            max_tokens=384,
            stage="decomposition",
        )
        subtasks = parsed.get("subtasks") if isinstance(parsed, dict) else None
        clean: list[dict[str, Any]] = []
        if isinstance(subtasks, list):
            for i, sub in enumerate(subtasks[:6], 1):
                if not isinstance(sub, dict):
                    continue
                goal = str(sub.get("goal") or "").strip()
                acceptance = sub.get("acceptance") if isinstance(sub.get("acceptance"), list) else []
                if goal:
                    clean.append({"id": str(sub.get("id") or f"task-{i}"), "goal": goal, "acceptance": acceptance})
        if len(clean) >= 2 or route.get("complexity") == "small":
            raw["decomposition_source"] = "llm"
            return clean, raw
        raise RuntimeError("decomposition returned too few usable subtasks")
    except Exception as exc:
        subtasks = heuristic_decompose(task, route)
        return subtasks, {
            "model": model,
            "response": "",
            "decomposition_source": "heuristic_fallback",
            "llm_decomposition_error": str(exc),
        }


base.decompose_task = decompose_with_fallback

if __name__ == "__main__":
    base.main()
