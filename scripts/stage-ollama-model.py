#!/usr/bin/env python3
"""Stage one Ollama model from cold UNAS storage to the host's local Ollama store.

Safety properties:
- dry-run by default;
- stages exactly one named model from a generated staging plan;
- requires --apply for writes;
- never deletes or evicts existing local artifacts;
- copies only blobs referenced by the selected manifest;
- verifies copied blob sizes and SHA-256 digests;
- writes the manifest only after all required blobs verify.

This is staging, not runtime loading. Ollama may discover the staged manifest after
completion; the script itself does not start a model or make an inference request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def sha256(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def load_plan(path: Path, model: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("items", []):
        if item.get("model") == model:
            return item
    raise SystemExit(f"model not found in staging plan: {model}")


def manifest_blob_refs(payload: dict) -> list[tuple[str, int | None]]:
    refs: list[tuple[str, int | None]] = []
    objects = []
    config = payload.get("config")
    if isinstance(config, dict):
        objects.append(config)
    layers = payload.get("layers", [])
    if isinstance(layers, list):
        objects.extend(x for x in layers if isinstance(x, dict))
    for obj in objects:
        digest = obj.get("digest")
        if isinstance(digest, str) and digest.startswith("sha256:"):
            size = obj.get("size")
            refs.append((digest, int(size) if isinstance(size, int) else None))
    return refs


def digest_filename(digest: str) -> str:
    return digest.replace(":", "-", 1)


def default_local_root() -> Path:
    env = os.environ.get("OLLAMA_MODELS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".ollama" / "models"


def target_manifest_path(local_root: Path, model: str) -> Path:
    if ":" in model:
        name, tag = model.rsplit(":", 1)
    else:
        name, tag = model, "latest"
    # Candidate matrix currently uses registry.ollama.ai/library models.
    return local_root / "manifests" / "registry.ollama.ai" / "library" / name / tag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--local-root", default=str(default_local_root()))
    ap.add_argument("--apply", action="store_true", help="Actually copy files; default is dry-run")
    args = ap.parse_args()

    item = load_plan(Path(args.plan), args.model)
    if item.get("action") != "stage_to_local_ssd":
        raise SystemExit(f"plan does not request staging for {args.model}: {item.get('action')}")

    source = item.get("preferred_source") or {}
    manifest_src = Path(str(source.get("manifest_path", "")))
    blob_src_root = Path(str(source.get("blob_root", "")))
    if not manifest_src.is_file():
        raise SystemExit(f"source manifest missing: {manifest_src}")
    if not blob_src_root.is_dir():
        raise SystemExit(f"source blob root missing: {blob_src_root}")

    manifest = json.loads(manifest_src.read_text(encoding="utf-8"))
    refs = manifest_blob_refs(manifest)
    if not refs:
        raise SystemExit("manifest contains no local sha256 blob references")

    local_root = Path(args.local_root).expanduser()
    local_blob_root = local_root / "blobs"
    manifest_dst = target_manifest_path(local_root, args.model)

    total = 0
    to_copy: list[tuple[Path, Path, str, int | None]] = []
    reused = 0
    for digest, declared_size in refs:
        src = blob_src_root / digest_filename(digest)
        dst = local_blob_root / digest_filename(digest)
        if not src.is_file():
            raise SystemExit(f"required source blob missing: {src}")
        actual_size = src.stat().st_size
        if declared_size is not None and actual_size != declared_size:
            raise SystemExit(f"source blob size mismatch for {digest}: manifest={declared_size}, file={actual_size}")
        total += actual_size
        if dst.is_file() and dst.stat().st_size == actual_size:
            reused += actual_size
            continue
        to_copy.append((src, dst, digest, declared_size))

    free = shutil.disk_usage(local_root if local_root.exists() else local_root.parent).free
    required = sum(src.stat().st_size for src, _, _, _ in to_copy)

    print(f"model: {args.model}")
    print(f"source manifest: {manifest_src}")
    print(f"local Ollama root: {local_root}")
    print(f"referenced bytes: {total}")
    print(f"already reusable locally: {reused}")
    print(f"bytes to copy: {required}")
    print(f"free bytes: {free}")
    print(f"target manifest: {manifest_dst}")

    if required > free:
        raise SystemExit("insufficient local disk space")

    if not args.apply:
        print("DRY RUN: no files changed. Re-run with --apply to stage this model.")
        return

    local_blob_root.mkdir(parents=True, exist_ok=True)
    for src, dst, digest, _ in to_copy:
        tmp = dst.with_name(dst.name + ".partial")
        print(f"copy {src.name} -> {dst}")
        shutil.copy2(src, tmp)
        expected = digest.split(":", 1)[1]
        actual = sha256(tmp)
        if actual != expected:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"SHA-256 verification failed for {digest}: got {actual}")
        tmp.replace(dst)

    # Verify reused blobs too before exposing the manifest locally.
    for digest, declared_size in refs:
        dst = local_blob_root / digest_filename(digest)
        if not dst.is_file():
            raise SystemExit(f"post-stage blob missing: {dst}")
        if declared_size is not None and dst.stat().st_size != declared_size:
            raise SystemExit(f"post-stage size mismatch: {dst}")
        expected = digest.split(":", 1)[1]
        if sha256(dst) != expected:
            raise SystemExit(f"post-stage SHA-256 mismatch: {dst}")

    manifest_dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_manifest = manifest_dst.with_name(manifest_dst.name + ".partial")
    shutil.copy2(manifest_src, tmp_manifest)
    tmp_manifest.replace(manifest_dst)
    print(f"STAGED: {args.model}")
    print("No model was loaded into memory. Verify with `ollama list` before benchmarking.")


if __name__ == "__main__":
    main()
