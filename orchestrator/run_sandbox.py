#!/usr/bin/env python3
"""Create an isolated Git worktree and ask a local worker model for a patch.

The script consumes a verified proposal produced by run_orchestrator.py.
It never modifies the source checkout. By default it creates the worktree,
generates a patch, validates paths and runs `git apply --check`, but does not
apply the patch. Pass --apply to apply the patch inside the temporary worktree.
Tests are never invented/executed by the model; an optional test command must be
provided explicitly by the operator with --test-command.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def post_json(url: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_generate(endpoint: str, model: str, prompt: str, ctx: int, max_tokens: int) -> str:
    raw = post_json(
        endpoint.rstrip("/") + "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_ctx": ctx, "num_predict": max_tokens, "temperature": 0},
        },
    )
    return str(raw.get("response", ""))


def extract_diff(text: str) -> str:
    s = text.strip()
    fence = re.search(r"```(?:diff|patch)?\s*(diff --git .*?)```", s, re.S | re.I)
    if fence:
        return fence.group(1).strip() + "\n"
    idx = s.find("diff --git ")
    if idx >= 0:
        return s[idx:].strip() + "\n"
    return ""


def safe_patch_paths(diff_text: str) -> tuple[bool, str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) < 4:
                return False, "malformed diff header"
            paths.extend(parts[2:4])
        elif line.startswith("+++ ") or line.startswith("--- "):
            value = line[4:].strip().split("\t", 1)[0]
            if value != "/dev/null":
                paths.append(value)
    for raw in paths:
        p = raw[2:] if raw.startswith(("a/", "b/")) else raw
        if not p or p.startswith("/") or ".." in Path(p).parts or p == ".git" or p.startswith(".git/"):
            return False, f"unsafe patch path: {raw}"
    return True, "ok"


def words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z0-9_.-]{3,}", text)}


def choose_context_files(repo: Path, task: str, proposal: dict[str, Any], limit: int = 8) -> list[Path]:
    tracked = run(["git", "ls-files"], cwd=repo).stdout.splitlines()
    query = words(task + " " + json.dumps(proposal, ensure_ascii=False))
    allowed = {".py", ".php", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".rb", ".sh", ".json", ".yaml", ".yml", ".md"}
    scored: list[tuple[float, Path]] = []
    for rel in tracked:
        p = repo / rel
        if p.suffix.lower() not in allowed or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")[:20000]
        except OSError:
            continue
        token_overlap = len(query & words(rel + " " + text))
        if token_overlap:
            scored.append((token_overlap / max(1, len(query)), p))
    scored.sort(key=lambda x: (-x[0], str(x[1])))
    return [p for _, p in scored[:limit]]


def make_prompt(task: str, proposal: dict[str, Any], files: list[Path], worktree: Path) -> str:
    chunks = []
    for p in files:
        rel = p.relative_to(worktree)
        text = p.read_text(encoding="utf-8", errors="ignore")[:20000]
        chunks.append(f"FILE: {rel}\n---\n{text}\n---")
    context = "\n\n".join(chunks) or "No likely source files were selected."
    return f"""You are a bounded patch-producing coding agent working in an isolated Git worktree.

TASK:
{task}

VERIFIED PROPOSAL:
{json.dumps(proposal, ensure_ascii=False, indent=2)}

REPOSITORY CONTEXT:
{context}

Return ONLY a unified Git diff beginning with `diff --git`.
Rules:
- change only files needed for the task;
- do not modify .git, CI secrets, credentials, lockfiles unless essential;
- preserve existing APIs unless the task explicitly changes them;
- include tests when the repository context reveals the appropriate test location;
- do not claim tests were run;
- do not output shell commands or commentary.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposal", required=True, help="verified orchestrator run JSON")
    ap.add_argument("--repo", required=True, help="Git repository to sandbox")
    ap.add_argument("--endpoint", default=os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434"))
    ap.add_argument("--worker-model", default="granite3.3:2b")
    ap.add_argument("--context", type=int, default=16384)
    ap.add_argument("--max-output-tokens", type=int, default=2048)
    ap.add_argument("--apply", action="store_true", help="apply validated patch inside sandbox worktree")
    ap.add_argument("--test-command", help="operator-supplied command to run only after --apply")
    ap.add_argument("--keep-worktree", action="store_true")
    ap.add_argument("--output-dir", default="artifacts/sandbox-runs")
    args = ap.parse_args()

    started = time.perf_counter()
    repo = Path(args.repo).resolve()
    proposal_path = Path(args.proposal).resolve()
    proposal_run = json.loads(proposal_path.read_text(encoding="utf-8"))
    if proposal_run.get("status") != "verified_proposal":
        raise SystemExit("proposal input must have status=verified_proposal")
    if not (repo / ".git").exists() and run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo, check=False).returncode != 0:
        raise SystemExit(f"not a Git repository: {repo}")

    task = str(proposal_run.get("task", "")).strip()
    proposal_artifacts = [r.get("worker", {}).get("artifact") for r in proposal_run.get("results", [])]
    proposal = {"subtasks": proposal_run.get("subtasks", []), "artifacts": proposal_artifacts}

    root_tmp = Path(tempfile.mkdtemp(prefix="hermes-next-sandbox-"))
    worktree = root_tmp / "worktree"
    base = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    run(["git", "worktree", "add", "--detach", str(worktree), base], cwd=repo)

    status = "sandbox_prepared"
    patch_text = ""
    patch_check = {"ok": False, "stdout": "", "stderr": ""}
    patch_applied = False
    test_result: dict[str, Any] | None = None
    selected_files: list[str] = []
    error: str | None = None

    try:
        files = choose_context_files(worktree, task, proposal)
        selected_files = [str(p.relative_to(worktree)) for p in files]
        prompt = make_prompt(task, proposal, files, worktree)
        response = ollama_generate(args.endpoint, args.worker_model, prompt, args.context, args.max_output_tokens)
        patch_text = extract_diff(response)
        if not patch_text:
            raise RuntimeError("worker did not return a unified git diff")
        safe, why = safe_patch_paths(patch_text)
        if not safe:
            raise RuntimeError(why)

        patch_file = root_tmp / "proposal.patch"
        patch_file.write_text(patch_text, encoding="utf-8")
        checked = run(["git", "apply", "--check", str(patch_file)], cwd=worktree, check=False)
        patch_check = {"ok": checked.returncode == 0, "stdout": checked.stdout, "stderr": checked.stderr}
        if checked.returncode != 0:
            status = "patch_check_failed"
        elif not args.apply:
            status = "patch_validated_not_applied"
        else:
            run(["git", "apply", str(patch_file)], cwd=worktree)
            patch_applied = True
            status = "patch_applied_in_sandbox"
            if args.test_command:
                test_started = time.perf_counter()
                test = subprocess.run(args.test_command, cwd=worktree, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                test_result = {
                    "command": args.test_command,
                    "returncode": test.returncode,
                    "stdout": test.stdout[-12000:],
                    "stderr": test.stderr[-12000:],
                    "wall_seconds": round(time.perf_counter() - test_started, 3),
                }
                status = "sandbox_tests_passed" if test.returncode == 0 else "sandbox_tests_failed"
    except Exception as exc:
        error = str(exc)
        status = "sandbox_error"

    diff_after = run(["git", "diff", "--no-ext-diff"], cwd=worktree, check=False).stdout if worktree.exists() else ""
    payload = {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "task": task,
        "source_proposal": str(proposal_path),
        "source_repo": str(repo),
        "base_commit": base,
        "worker_model": args.worker_model,
        "selected_context_files": selected_files,
        "worktree": str(worktree),
        "patch_check": patch_check,
        "patch_applied": patch_applied,
        "patch": patch_text,
        "sandbox_diff": diff_after,
        "test_result": test_result,
        "error": error,
        "safety": {
            "source_checkout_modified": False,
            "model_generated_commands_executed": False,
            "tests_require_operator_supplied_command": True,
        },
        "wall_seconds": round(time.perf_counter() - started, 3),
    }

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = outdir / f"sandbox-run-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"status: {status}")
    print(f"patch_check: {patch_check['ok']}")
    print(f"patch_applied: {patch_applied}")
    if test_result is not None:
        print(f"tests: returncode={test_result['returncode']}")
    if error:
        print(f"error: {error}")
    print(f"worktree: {worktree}")
    print(out)

    if not args.keep_worktree:
        run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo, check=False)
        shutil.rmtree(root_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
