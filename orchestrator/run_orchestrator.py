#!/usr/bin/env python3
"""Standalone Hermes Next local orchestrator prototype.

Flow:
  task
   -> local knowledge retrieval
   -> route / complexity decision
   -> optional decomposition
   -> bounded local worker execution
   -> independent tester review
   -> verification gate
   -> structured run log

Safety:
- read-only against project repositories;
- never applies patches or executes generated code;
- never downloads/stages/evicts models;
- external escalation is recorded as a recommendation only.

This prototype intentionally sits outside the user's active Hermes profile.
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
from typing import Any


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
    wall = time.perf_counter() - started
    return {
        "model": model,
        "response": raw.get("response", ""),
        "done_reason": raw.get("done_reason"),
        "wall_seconds": round(wall, 3),
        "output_tokens": int(raw.get("eval_count", 0) or 0),
    }


def extract_json(text: str) -> Any:
    """Parse plain/fenced JSON or the first balanced JSON object in model output."""
    s = (text or "").strip()
    if not s:
        return None

    try:
        return json.loads(s)
    except Exception:
        pass

    # Common model behavior: fenced JSON despite 'JSON only'.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    # Find the first balanced object while respecting JSON strings/escapes.
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
                    candidate = s[start:i + 1]
                    try:
                        return json.loads(candidate)
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
) -> tuple[Any, dict[str, Any]]:
    """Use Ollama JSON mode and retry once if the model still returns invalid JSON."""
    raw = ollama_generate(endpoint, model, prompt, ctx=ctx, max_tokens=max_tokens, json_mode=True)
    parsed = extract_json(raw["response"])
    if isinstance(parsed, dict):
        raw["parse_attempts"] = 1
        return parsed, raw

    retry_prompt = (
        "Your previous response was not valid JSON. Output exactly one JSON object and nothing else. "
        "No markdown, no code fences, no explanation.\n\n" + prompt
    )
    retry = ollama_generate(endpoint, model, retry_prompt, ctx=ctx, max_tokens=max_tokens, json_mode=True)
    retry["parse_attempts"] = 2
    retry["first_response"] = raw.get("response", "")
    parsed = extract_json(retry["response"])
    if not isinstance(parsed, dict):
        preview = (retry.get("response") or "").replace("\n", " ")[:500]
        raise RuntimeError(f"{stage} returned invalid JSON after retry; response={preview!r}")
    return parsed, retry


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
            tokens = words(sample)
            overlap = len(query & tokens)
            if overlap == 0:
                continue
            score = overlap / max(1, len(query))
            snippet = " ".join(sample.replace("\n", " ").split())[:600]
            hits.append({"path": str(path), "score": round(score, 3), "snippet": snippet})
    hits.sort(key=lambda x: (-x["score"], x["path"]))
    return hits[:limit]


def route_task(endpoint: str, model: str, task: str, knowledge: list[dict[str, Any]], ctx: int) -> tuple[dict[str, Any], dict[str, Any]]:
    knowledge_text = "\n".join(f"- {h['path']}: {h['snippet']}" for h in knowledge) or "- none found"
    prompt = f"""You are the Hermes Next routing agent. Return JSON only.

Task:
{task}

Previously retrieved local knowledge:
{knowledge_text}

Choose one primary capability from:
- code.implement.small
- code.implement
- code.review
- test.design
- planning.decomposition
- research.web.current
- structured_output
- summarization.compact

Return exactly:
{{
  "capability": "...",
  "complexity": "small|medium|large",
  "needs_decomposition": true,
  "needs_current_web": false,
  "reason": "short reason"
}}
"""
    parsed, raw = generate_json_with_retry(
        endpoint, model, prompt, ctx=ctx, max_tokens=384, stage="router"
    )
    return parsed, raw


def decompose_task(endpoint: str, model: str, task: str, route: dict[str, Any], knowledge: list[dict[str, Any]], ctx: int) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not route.get("needs_decomposition"):
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], None

    prompt = f"""You are a local decomposition agent. Return JSON only.
Break the request into the fewest independently verifiable bounded subtasks.
Do not perform the work.

Request:
{task}

Routing decision:
{json.dumps(route, ensure_ascii=False)}

Return:
{{"subtasks":[{{"id":"task-1","goal":"...","acceptance":["..."]}}]}}
"""
    try:
        parsed, raw = generate_json_with_retry(
            endpoint, model, prompt, ctx=ctx, max_tokens=512, stage="decomposition"
        )
    except RuntimeError as exc:
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], {
            "model": model,
            "response": "",
            "error": str(exc),
            "fallback_used": True,
        }
    subtasks = parsed.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], raw
    clean = []
    for i, sub in enumerate(subtasks[:8], 1):
        if not isinstance(sub, dict):
            continue
        clean.append({
            "id": str(sub.get("id") or f"task-{i}"),
            "goal": str(sub.get("goal") or "").strip(),
            "acceptance": sub.get("acceptance") if isinstance(sub.get("acceptance"), list) else [],
        })
    return clean or [{"id": "task-1", "goal": task, "acceptance": ["satisfy the requested change"]}], raw


def run_worker(endpoint: str, model: str, task: str, subtask: dict[str, Any], knowledge: list[dict[str, Any]], ctx: int) -> dict[str, Any]:
    knowledge_text = "\n".join(f"- {h['path']}: {h['snippet']}" for h in knowledge) or "- none"
    prompt = f"""You are the bounded local implementation worker.
This is a READ-ONLY prototype: do not claim files were modified or commands were executed.
Produce a proposed implementation artifact for later application/review.

Overall request:
{task}

Subtask:
{json.dumps(subtask, ensure_ascii=False)}

Retrieved project knowledge:
{knowledge_text}

Return JSON only:
{{
  "status": "proposed",
  "summary": "...",
  "proposed_changes": [{{"target":"file/module or unknown","change":"..."}}],
  "assumptions": ["..."],
  "verification_needed": ["..."]
}}
"""
    try:
        parsed, raw = generate_json_with_retry(
            endpoint, model, prompt, ctx=ctx, max_tokens=768, stage="worker"
        )
    except RuntimeError as exc:
        raw = {"model": model, "response": "", "error": str(exc)}
        parsed = None
    return {"subtask": subtask, "raw": raw, "artifact": parsed}


def run_tester(endpoint: str, model: str, task: str, worker_result: dict[str, Any], ctx: int) -> dict[str, Any]:
    artifact = worker_result.get("artifact")
    prompt = f"""You are the independent Hermes Next tester/reviewer.
Evaluate the proposed artifact against the task and subtask acceptance criteria.
Do not trust the implementer's conclusions. Do not rewrite the implementation.
Return JSON only.

Overall request:
{task}

Subtask:
{json.dumps(worker_result.get('subtask'), ensure_ascii=False)}

Proposed artifact:
{json.dumps(artifact, ensure_ascii=False)}

Return:
{{
  "pass": true,
  "blocking_issues": ["..."],
  "missing_tests": ["..."],
  "verification_steps": ["..."],
  "confidence": "low|medium|high"
}}
"""
    try:
        parsed, raw = generate_json_with_retry(
            endpoint, model, prompt, ctx=ctx, max_tokens=640, stage="tester"
        )
    except RuntimeError as exc:
        raw = {"model": model, "response": "", "error": str(exc)}
        parsed = None
    return {"raw": raw, "evaluation": parsed}


def verification_gate(worker: dict[str, Any], tester: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    artifact = worker.get("artifact")
    evaluation = tester.get("evaluation")
    if not isinstance(artifact, dict):
        reasons.append("worker_invalid_json")
    if not isinstance(evaluation, dict):
        reasons.append("tester_invalid_json")
        return False, reasons
    if evaluation.get("pass") is not True:
        reasons.append("tester_rejected")
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

    task = args.task
    if args.task_file:
        task = Path(args.task_file).read_text(encoding="utf-8")
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
        events.append({"state": "routing", "decision": route})

        if route.get("needs_current_web") or route.get("capability") == "research.web.current":
            final = {
                "schema_version": 2,
                "status": "external_escalation_recommended",
                "task": task,
                "knowledge": knowledge,
                "route": route,
                "router_raw": route_raw,
                "events": events,
                "note": "Prototype does not call external providers. Hermes integration should apply escalation policy.",
            }
        else:
            subtasks, decomposition_raw = decompose_task(args.endpoint, args.router_model, task, route, knowledge, args.context)
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
                "schema_version": 2,
                "status": "verified_proposal" if all_pass else "verification_failed",
                "task": task,
                "models": {
                    "router": args.router_model,
                    "worker": args.worker_model,
                    "tester": args.tester_model,
                },
                "knowledge": knowledge,
                "route": route,
                "router_raw": route_raw,
                "decomposition_raw": decomposition_raw,
                "subtasks": subtasks,
                "results": results,
                "events": events,
                "safety": {
                    "read_only": True,
                    "patches_applied": False,
                    "commands_executed": False,
                    "external_provider_called": False,
                },
            }
    except Exception as exc:
        events.append({"state": "error", "error": str(exc)})
        final = {
            "schema_version": 2,
            "status": "orchestrator_error",
            "task": task,
            "models": {
                "router": args.router_model,
                "worker": args.worker_model,
                "tester": args.tester_model,
            },
            "knowledge": knowledge,
            "events": events,
            "error": str(exc),
            "safety": {
                "read_only": True,
                "patches_applied": False,
                "commands_executed": False,
                "external_provider_called": False,
            },
        }

    final["wall_seconds"] = round(time.perf_counter() - started, 3)
    final["captured_at_utc"] = datetime.now(timezone.utc).isoformat()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"orchestrator-run-{stamp}.json"
    out.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"status: {final['status']}")
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
