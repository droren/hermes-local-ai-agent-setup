#!/usr/bin/env python3
"""Dependency-light capability benchmark runner for Ollama-compatible models."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def post_json(url: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def memory_snapshot() -> dict:
    result = {"source": "vm_stat"}
    try:
        text = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)
        page_size = 16384
        first = text.splitlines()[0]
        if "page size of" in first:
            page_size = int(first.split("page size of", 1)[1].split("bytes", 1)[0].strip())
        values = {}
        for line in text.splitlines()[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            values[key.strip()] = int(value.strip().rstrip("."))
        used_keys = ["Pages active", "Pages inactive", "Pages speculative", "Pages wired down", "Pages occupied by compressor"]
        used = sum(values.get(k, 0) for k in used_keys) * page_size
        result["estimated_used_gb"] = round(used / 1024**3, 3)
    except Exception as exc:
        result = {"source": "unavailable", "error": str(exc)}
    return result


def write_record(args, started: float, before: dict, response: dict | None, error: str | None) -> Path:
    wall = time.perf_counter() - started
    after = memory_snapshot()
    response = response or {}
    eval_count = int(response.get("eval_count", 0) or 0)
    eval_duration_ns = int(response.get("eval_duration", 0) or 0)
    prompt_count = int(response.get("prompt_eval_count", 0) or 0)
    prompt_duration_ns = int(response.get("prompt_eval_duration", 0) or 0)
    load_duration_ns = int(response.get("load_duration", 0) or 0)
    tps = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns else None

    record = {
        "schema_version": 2,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "backend": "ollama",
        "endpoint": args.endpoint,
        "model": args.model,
        "capability": args.capability,
        "prompt_file": args.prompt_file,
        "context_requested": args.context,
        "max_output_tokens": args.max_output_tokens,
        "timeout_seconds": args.timeout,
        "status": "error" if error else "completed",
        "error": error,
        "metrics": {
            "wall_seconds": round(wall, 3),
            "load_seconds": round(load_duration_ns / 1e9, 3),
            "prompt_tokens": prompt_count,
            "prompt_eval_seconds": round(prompt_duration_ns / 1e9, 3),
            "output_tokens": eval_count,
            "generation_seconds": round(eval_duration_ns / 1e9, 3),
            "generation_tokens_per_second": round(tps, 3) if tps is not None else None,
            "memory_before": before,
            "memory_after": after,
        },
        "response": response.get("response", ""),
        "done_reason": response.get("done_reason"),
        "evaluation": {
            "automatic_score": None,
            "human_score": None,
            "human_corrections": None,
            "accepted": False if error else None,
            "notes": None,
        },
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_model = args.model.replace("/", "_").replace(":", "_")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"{stamp}-{safe_model}-{args.capability.replace('.', '_')}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--capability", required=True)
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--endpoint", default=os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434"))
    p.add_argument("--context", type=int, default=8192)
    p.add_argument("--max-output-tokens", type=int, default=384)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--output-dir", default="artifacts/benchmarks")
    args = p.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    before = memory_snapshot()
    started = time.perf_counter()
    response = None
    error = None
    try:
        response = post_json(
            args.endpoint.rstrip("/") + "/api/generate",
            {
                "model": args.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": args.context,
                    "num_predict": args.max_output_tokens,
                    "temperature": 0,
                },
            },
            args.timeout,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    out = write_record(args, started, before, response, error)
    print(out)
    if error:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
