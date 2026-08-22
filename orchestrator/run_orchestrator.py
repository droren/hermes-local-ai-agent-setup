#!/usr/bin/env python3
"""Standalone Hermes Next local orchestrator prototype.

Flow:
  task -> local retrieval -> route -> optional decomposition -> proposal worker
       -> proposal-aware tester -> verification gate -> structured run log

Safety:
- read-only against project repositories;
- never applies patches or executes generated code;
- never downloads/stages/evicts models;
- external escalation is recorded as a recommendation only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ALLOWED_CAPABILITIES = {
    "code.implement.small",
    "code.implement",
    "code.review",
    "test.design",
    "planning.decomposition",
    "research.web.current",
    "structured_output",
    "summarization.compact",
}


def post_json(url: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_generate(
    endpoint: str,
    model: str,
    prompt: str,
    *,
    ctx: int,
    max_tokens: int,
    json_mode: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "num_ctx": ctx,
            "num_predict": max_tokens,
            "temperature": 0,
        },
    }
    if json_mode:
        payload["format"] = "json"
    raw = post_json(endpoint.rstrip("/") + "/api/generate", payload)
    return {
        "model": model,
        "response": raw.get("response", ""),
        "done_reason": raw.get("done_reason"),
        "wall_seconds": round(time.perf_counter() - started, 3),
        "output_tokens": int(raw.get("eval_count", 0) or 0),
    }


def extract_json(text: str) -> Any:
    s = (text or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, flags=re.I | re.S)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    for start, ch in enumerate(s):
        if ch != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(s)):
            c = s[i]
            if in_string:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    in_string = False
                continue
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        break
    return None


def generate_json_with_retry(
    endpoint: str,
    model: str,
    prompt: str,
    *,
    ctx: int,
    max_tokens: int,
    stage: str,
    validator: Callable[[dict[str, Any]], tuple[bool, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retry once on invalid JSON *or* schema-invalid JSON."""
    first = ollama_generate(endpoint, model, prompt, ctx=ctx, max_tokens=max_tokens, json_mode=True)
    parsed = extract_json(first["response"])
    valid = isinstance(parsed, dict)
    reason = "invalid_json"
    if valid and validator:
        valid, reason = validator(parsed)
    if valid:
        first["parse_attempts"] = 1
        return parsed, first

    retry_prompt = (
        "Your previous answer was unusable. Return exactly one complete JSON object matching the requested schema. "
        f"Validation failure: {reason}. Do not return an empty object. No markdown or explanation.\n\n" + prompt
    )
    retry = ollama_generate(endpoint, model, retry_prompt, ctx=ctx, max_tokens=max_tokens, json_mode=True)
    retry["parse_attempts"] = 2
    retry["first_response"] = first.get("response", "")
    retry["first_validation_error"] = reason
    parsed = extract_json(retry["response"])
    valid = isinstance(parsed, dict)
    reason = "invalid_json"
    if valid and validator:
        valid, reason = validator(parsed)
    if not valid:
        preview = (retry.get("response") or "").replace("\n", " ")[:500]
        raise RuntimeError(f"{stage} returned invalid result after retry ({reason}); response={preview!r}")
    return parsed, retry


def validate_route(obj: dict[str, Any]) -> tuple[bool, str]:
    cap = obj.get("capability")
    complexity = obj.get("complexity")
    if cap not in ALLOWED_CAPABILITIES:
        return False, "missing_or_invalid_capability"
    if complexity not in {"small", "medium", "large"}:
        return False, "missing_or_invalid_complexity"
    if not isinstance(obj.get("needs_decomposition"), bool):
        return False, "needs_decomposition_must_be_boolean"
    if not isinstance(obj.get("needs_current_web"), bool):
        return False, "needs_current_web_must_be_boolean"
    if not isinstance(obj.get("reason"), str) or not obj["reason"].strip():
        return False, "reason_required"
    return True, "ok"


def validate_worker(obj: dict[str, Any]) -> tuple[bool, str]:
    if obj.get("status") != "proposed":
        return False, "status_must_be_proposed"
    changes = obj.get("proposed_changes")
    if not isinstance(changes, list) or not changes:
        return False, "proposed_changes_required"
    if not isinstance(obj.get("verification_needed"), list) or not obj["verification_needed"]:
        return False, "verification_needed_required"
    return True, "ok"


def validate_tester(obj: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(obj.get("pass"), bool):
        return False, "pass_must_be_boolean"
    for field in ("blocking_issues", "missing_tests", "verification_steps"):
        if not isinstance(obj.get(field), list):
            return False, f"{field}_must_be_list"
    if obj.get("confidence") not in {"low", "medium", "high"}:
        return False, "invalid_confidence"
    return True, "ok"


def words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z0-9_./:-]{3,}", text)}


def retrieve_local(task: str, roots: list[str], limit: int = 6) -> list[dict[str, Any]]:
    query = words(task)
    if not query:
        return []
    hits: list[dict[str, Any]] = []
    allowed = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".sh"}
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            if any(part in {".git", "node_modules", "venv", ".venv"} for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            sample = text[:12000]
            overlap = len(query & words(sample))
            if overlap:
                hits.append({
                    "path": str(path),
                    "score": round(overlap / max(1, len(query)), 3),
                    "snippet": " ".join(sample.replace("\n", " ").split())[:600],
                })
    hits.sort(key=lambda x: (-x["score"], x["path"]))
    return hits[:limit]


def heuristic_route(task: str) -> dict[str, Any]:
    """Deterministic local fallback. Routing must never be a single point of failure."""
    low = task.lower()

    web_terms = ("latest", "current news", "today", "web search", "internet search", "look up online", "research online")
    review_terms = ("review", "audit", "inspect code", "find bugs", "code quality")
    test_terms = ("design tests", "test design", "write tests", "add tests", "boundary tests", "regression tests")
    planning_terms = ("architecture", "architect", "plan the", "decompose", "break down", "migration plan")
    summary_terms = ("summarize", "summary", "condense")
    structured_terms = ("extract json", "return json", "structured output", "parse into")
    code_terms = (
        "add ", "implement", "fix ", "change ", "modify", "refactor", "validation",
        "api", "function", "class", "php", "python", "javascript", "typescript", "code",
    )

    needs_web = any(term in low for term in web_terms)
    if needs_web:
        capability = "research.web.current"
    elif any(term in low for term in review_terms) and not any(term in low for term in code_terms):
        capability = "code.review"
    elif any(term in low for term in planning_terms):
        capability = "planning.decomposition"
    elif any(term in low for term in summary_terms):
        capability = "summarization.compact"
    elif any(term in low for term in structured_terms):
        capability = "structured_output"
    elif any(term in low for term in test_terms) and not any(term in low for term in code_terms):
        capability = "test.design"
    elif any(term in low for term in code_terms):
        capability = "code.implement.small"
    else:
        capability = "planning.decomposition"

    objective_markers = sum(
        1 for term in (
            " and ", " also ", " preserve ", " without changing", " add tests", " boundary tests",
            " regression tests", " migrate ", " across ", " multiple ",
        )
        if term in low
    )
    large_markers = any(term in low for term in ("architecture", "migration", "multiple services", "entire", "whole system", "across repositories"))
    if large_markers or len(task) > 700:
        complexity = "large"
    elif objective_markers >= 2 or len(task) > 220:
        complexity = "medium"
    else:
        complexity = "small"

    needs_decomposition = complexity != "small" or objective_markers >= 2
    if capability in {"code.review", "test.design", "summarization.compact", "structured_output"} and complexity == "small":
        needs_decomposition = False

    return {
        "capability": capability,
        "complexity": complexity,
        "needs_decomposition": needs_decomposition,
        "needs_current_web": needs_web,
        "reason": "deterministic fallback after local LLM router failed schema validation",
    }


def route_task(endpoint: str, model: str, task: str, knowledge: list[dict[str, Any]], ctx: int):
    # Retrieval happens before routing, but routing only needs evidence that prior knowledge exists.
    # Feeding full retrieved snippets to a tiny classifier made qwen3:1.7b collapse to `{}`.
    knowledge_paths = [h["path"] for h in knowledge[:4]]
    knowledge_summary = (
        f"{len(knowledge)} local knowledge hits found. Top paths: " + ", ".join(knowledge_paths)
        if knowledge else "No local knowledge hits found."
    )
    prompt = f"""You are a task classifier. Do not solve the task.

TASK:
{task}

KNOWLEDGE STATUS:
{knowledge_summary}

Choose exactly one capability from this list:
code.implement.small, code.implement, code.review, test.design, planning.decomposition, research.web.current, structured_output, summarization.compact

Return one JSON object with these exact fields and no others:
{{"capability":"code.implement.small","complexity":"small","needs_decomposition":false,"needs_current_web":false,"reason":"short reason"}}

Replace the example values with your classification. Never return an empty object.
"""
    try:
        parsed, raw = generate_json_with_retry(
            endpoint, model, prompt, ctx=min(ctx, 4096), max_tokens=192, stage="router", validator=validate_route
        )
        raw["routing_source"] = "llm"
        return parsed, raw
    except RuntimeError as exc:
        route = heuristic_route(task)
        raw = {
            "model": model,
            "response": "",
            "routing_source": "heuristic_fallback",
            "llm_router_error": str(exc),
            "knowledge_hits_seen": len(knowledge),
        }
        return route, raw


def decompose_task(endpoint: str, model: str, task: str, route: dict[str, Any], ctx: int):
    if not route.get("needs_decomposition"):
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], None
    prompt = f"""You are a local decomposition agent. Break the request into the fewest independently verifiable bounded subtasks. Do not perform the work.

Request: {task}
Routing decision: {json.dumps(route, ensure_ascii=False)}

Return JSON:
{{"subtasks":[{{"id":"task-1","goal":"...","acceptance":["specific verifiable criterion"]}}]}}
"""
    try:
        parsed, raw = generate_json_with_retry(endpoint, model, prompt, ctx=ctx, max_tokens=512, stage="decomposition")
    except RuntimeError as exc:
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], {"error": str(exc), "fallback_used": True}
    subtasks = parsed.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], raw
    clean = []
    for i, sub in enumerate(subtasks[:8], 1):
        if not isinstance(sub, dict):
            continue
        goal = str(sub.get("goal") or "").strip()
        acceptance = sub.get("acceptance") if isinstance(sub.get("acceptance"), list) else []
        if goal:
            clean.append({"id": str(sub.get("id") or f"task-{i}"), "goal": goal, "acceptance": acceptance})
    return clean or [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], raw


def run_worker(endpoint: str, model: str, task: str, subtask: dict[str, Any], knowledge: list[dict[str, Any]], ctx: int):
    knowledge_text = "\n".join(f"- {h['path']}: {h['snippet']}" for h in knowledge) or "- none"
    prompt = f"""You are the bounded local implementation worker in READ-ONLY PROPOSAL MODE.
Nothing has been changed yet. Never say a change was 'added', 'implemented', 'fixed', or 'verified'. Describe what SHOULD be changed.
Be concrete enough that a later patch-producing agent can implement the proposal.

Overall request:
{task}

Subtask:
{json.dumps(subtask, ensure_ascii=False)}

Retrieved project knowledge:
{knowledge_text}

Return JSON:
{{
  "status": "proposed",
  "summary": "proposal summary using future/conditional wording",
  "proposed_changes": [{{"target":"specific file/module or unknown","change":"specific intended change"}}],
  "assumptions": ["..."],
  "test_cases": [{{"input":"...","expected":"..."}}],
  "verification_needed": ["specific check that can be executed later"]
}}
"""
    try:
        parsed, raw = generate_json_with_retry(
            endpoint, model, prompt, ctx=ctx, max_tokens=768, stage="worker", validator=validate_worker
        )
    except RuntimeError as exc:
        return {"subtask": subtask, "raw": {"model": model, "error": str(exc)}, "artifact": None}
    return {"subtask": subtask, "raw": raw, "artifact": parsed}


def run_tester(endpoint: str, model: str, task: str, worker_result: dict[str, Any], ctx: int):
    artifact = worker_result.get("artifact")
    prompt = f"""You are the independent Hermes Next proposal reviewer/test designer.
THIS IS READ-ONLY PROPOSAL MODE. No patch exists and no tests have been executed yet.
Do NOT reject merely because execution evidence, logs, or applied code are absent.
Instead judge whether the proposal is internally consistent, preserves the stated constraints, identifies the intended change, and contains sufficient future verification/test steps to proceed safely to a sandbox implementation stage.
Reject only for genuine proposal defects: missing requirement coverage, contradictory behavior, unsafe assumptions, incorrect boundaries, missing essential tests, or an implementation plan too vague to execute.

Overall request:
{task}

Subtask:
{json.dumps(worker_result.get('subtask'), ensure_ascii=False)}

Proposed artifact:
{json.dumps(artifact, ensure_ascii=False)}

Return JSON:
{{
  "pass": true,
  "blocking_issues": [],
  "missing_tests": [],
  "verification_steps": ["checks to run after a sandbox patch exists"],
  "confidence": "low|medium|high"
}}
"""
    try:
        parsed, raw = generate_json_with_retry(
            endpoint, model, prompt, ctx=ctx, max_tokens=640, stage="tester", validator=validate_tester
        )
    except RuntimeError as exc:
        return {"raw": {"model": model, "error": str(exc)}, "evaluation": None}
    return {"raw": raw, "evaluation": parsed}


def verification_gate(worker: dict[str, Any], tester: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    artifact = worker.get("artifact")
    evaluation = tester.get("evaluation")
    if not isinstance(artifact, dict):
        reasons.append("worker_invalid_json")
    if not isinstance(evaluation, dict):
        reasons.append("tester_invalid_json")
        return False, reasons
    if evaluation.get("pass") is not True:
        reasons.append("tester_rejected")
    if evaluation.get("blocking_issues"):
        reasons.append("blocking_issues_present")
    if tester.get("raw", {}).get("done_reason") == "length":
        reasons.append("tester_hit_output_limit")
    if worker.get("raw", {}).get("done_reason") == "length":
        reasons.append("worker_hit_output_limit")
    return not reasons, reasons


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="?", help="Task text; alternatively use --task-file")
    ap.add_argument("--task-file")
    ap.add_argument("--endpoint", default=os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434"))
    ap.add_argument("--router-model", default="qwen3:1.7b")
    ap.add_argument("--worker-model", default="granite3.3:2b")
    ap.add_argument("--tester-model", default="ministral-3:3b")
    ap.add_argument("--knowledge-root", action="append", default=[])
    ap.add_argument("--context", type=int, default=8192)
    ap.add_argument("--output-dir", default="artifacts/orchestrator-runs")
    args = ap.parse_args()

    task = Path(args.task_file).read_text(encoding="utf-8") if args.task_file else args.task
    if not task or not task.strip():
        raise SystemExit("provide task text or --task-file")
    task = task.strip()
    roots = args.knowledge_root or ["docs", "knowledge", "experience", "config"]
    started = time.perf_counter()
    events: list[dict[str, Any]] = []
    knowledge = retrieve_local(task, roots)
    events.append({"state": "retrieval", "hits": len(knowledge)})

    try:
        route, route_raw = route_task(args.endpoint, args.router_model, task, knowledge, args.context)
        events.append({
            "state": "routing",
            "decision": route,
            "source": route_raw.get("routing_source", "unknown"),
        })

        if route.get("needs_current_web") or route.get("capability") == "research.web.current":
            final = {
                "schema_version": 4,
                "status": "external_escalation_recommended",
                "task": task,
                "knowledge": knowledge,
                "route": route,
                "router_raw": route_raw,
                "events": events,
                "note": "Prototype does not call external providers. Hermes integration should apply escalation policy.",
            }
        else:
            subtasks, decomposition_raw = decompose_task(args.endpoint, args.router_model, task, route, args.context)
            events.append({"state": "decomposition", "subtask_count": len(subtasks)})
            results = []
            all_pass = True
            for subtask in subtasks:
                worker = run_worker(args.endpoint, args.worker_model, task, subtask, knowledge, args.context)
                events.append({"state": "worker", "subtask": subtask["id"], "model": args.worker_model})
                tester = run_tester(args.endpoint, args.tester_model, task, worker, args.context)
                events.append({"state": "tester", "subtask": subtask["id"], "model": args.tester_model})
                passed, reasons = verification_gate(worker, tester)
                all_pass = all_pass and passed
                results.append({
                    "subtask": subtask,
                    "worker": worker,
                    "tester": tester,
                    "verification": {"pass": passed, "reasons": reasons},
                })
            final = {
                "schema_version": 4,
                "status": "verified_proposal" if all_pass else "verification_failed",
                "task": task,
                "models": {"router": args.router_model, "worker": args.worker_model, "tester": args.tester_model},
                "knowledge": knowledge,
                "route": route,
                "router_raw": route_raw,
                "decomposition_raw": decomposition_raw,
                "subtasks": subtasks,
                "results": results,
                "events": events,
                "safety": {
                    "mode": "read_only_proposal",
                    "patches_applied": False,
                    "commands_executed": False,
                    "external_provider_called": False,
                },
            }
    except Exception as exc:
        events.append({"state": "error", "error": str(exc)})
        final = {
            "schema_version": 4,
            "status": "orchestrator_error",
            "task": task,
            "models": {"router": args.router_model, "worker": args.worker_model, "tester": args.tester_model},
            "knowledge": knowledge,
            "events": events,
            "error": str(exc),
            "safety": {"mode": "read_only_proposal", "patches_applied": False, "commands_executed": False, "external_provider_called": False},
        }

    final["wall_seconds"] = round(time.perf_counter() - started, 3)
    final["captured_at_utc"] = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"orchestrator-run-{stamp}.json"
    out.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"status: {final['status']}")
    if final.get("route"):
        source = (final.get("router_raw") or {}).get("routing_source", "unknown")
        print(f"route: {final['route'].get('capability')} ({final['route'].get('complexity')}, source={source})")
    if "subtasks" in final:
        print(f"subtasks: {len(final['subtasks'])}")
        passed = sum(1 for r in final.get("results", []) if r.get("verification", {}).get("pass"))
        print(f"verified: {passed}/{len(final.get('results', []))}")
    if final.get("error"):
        print(f"error: {final['error']}")
    print(f"wall_seconds: {final['wall_seconds']}")
    print(out)


if __name__ == "__main__":
    main()
