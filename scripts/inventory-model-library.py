#!/usr/bin/env python3
"""Inventory a shared/cold model library without activating or downloading models.

The goal is to distinguish:
  active       - currently exposed by a runtime (handled by inventory-host.sh)
  available    - model artifacts present in the shared library
  activatable  - available model with enough metadata to wire into a supported runtime

No model files are modified and large blobs are not checksummed by default.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def bytes_gb(value: int) -> float:
    return round(value / 1024**3, 3)


def path_size(root: Path) -> int:
    total = 0
    try:
        for base, _, files in os.walk(root):
            for name in files:
                try:
                    total += (Path(base) / name).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def candidate_bases(explicit: list[str]) -> list[Path]:
    values: list[str] = []
    values.extend(explicit)
    env = os.environ.get("HERMES_MODEL_LIBRARY_ROOTS", "")
    if env:
        values.extend(p for p in env.split(os.pathsep) if p)

    # Support both the newer UNAS mount naming and the older ModelStore mount.
    values.extend([
        "/Volumes/Shared_ModelDrive/ModelDrive",
        "/Volumes/ModelStore",
    ])

    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        p = Path(value).expanduser()
        key = str(p)
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


def locate(base: Path, suffixes: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for suffix in suffixes:
        p = base / suffix
        if p.exists():
            found.append(p)
    return found


def ollama_models(root: Path) -> list[dict]:
    manifests = root / "manifests"
    blobs = root / "blobs"
    if not manifests.exists():
        return []

    entries: list[dict] = []
    for manifest in manifests.rglob("*"):
        if not manifest.is_file():
            continue
        try:
            rel = manifest.relative_to(manifests)
            parts = rel.parts
            if len(parts) < 4:
                continue
            registry, namespace = parts[0], parts[1]
            tag = parts[-1]
            model_name = "/".join(parts[2:-1])
            display = f"{namespace}/{model_name}:{tag}" if namespace != "library" else f"{model_name}:{tag}"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            layers = payload.get("layers", [])
            config = payload.get("config", {})
            declared_size = sum(int(x.get("size", 0) or 0) for x in layers) + int(config.get("size", 0) or 0)
            digests = [x.get("digest") for x in [config, *layers] if x.get("digest")]
            missing_blobs = []
            if blobs.exists():
                for digest in digests:
                    # Ollama maps sha256:abc to blobs/sha256-abc.
                    blob = blobs / digest.replace(":", "-")
                    if not blob.exists():
                        missing_blobs.append(digest)

            entries.append({
                "id": f"ollama:{display}",
                "name": display,
                "source": "ollama",
                "state": "activatable" if not missing_blobs else "available_incomplete",
                "library_path": str(manifest),
                "registry": registry,
                "namespace": namespace,
                "tag": tag,
                "declared_size_gb": bytes_gb(declared_size),
                "blob_count": len(digests),
                "missing_blob_count": len(missing_blobs),
            })
        except Exception as exc:
            entries.append({
                "id": f"ollama-manifest:{manifest}",
                "name": manifest.name,
                "source": "ollama",
                "state": "inventory_error",
                "library_path": str(manifest),
                "error": str(exc),
            })
    return entries


def hf_models(root: Path) -> list[dict]:
    hub = root / "hub" if (root / "hub").exists() else root
    if not hub.exists():
        return []
    entries: list[dict] = []
    for model_dir in sorted(hub.glob("models--*")):
        if not model_dir.is_dir():
            continue
        raw = model_dir.name[len("models--"):]
        repo = raw.replace("--", "/")
        snapshots = model_dir / "snapshots"
        snapshot_ids = [p.name for p in snapshots.iterdir() if p.is_dir()] if snapshots.exists() else []
        size = path_size(model_dir)
        lower = repo.lower()
        runtime_hints = []
        if "mlx" in lower or "mlx-community" in lower:
            runtime_hints.append("mlx")
        runtime_hints.append("transformers")
        entries.append({
            "id": f"huggingface:{repo}",
            "name": repo,
            "source": "huggingface",
            "state": "activatable" if snapshot_ids and size > 0 else "available_incomplete",
            "library_path": str(model_dir),
            "size_gb": bytes_gb(size),
            "snapshots": snapshot_ids,
            "runtime_hints": sorted(set(runtime_hints)),
        })
    return entries


def comfy_models(root: Path) -> list[dict]:
    if not root.exists():
        return []
    entries: list[dict] = []
    allowed = {".safetensors", ".gguf", ".ckpt", ".pth", ".pt"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        if "/.cache/" in str(path):
            continue
        try:
            rel = path.relative_to(root)
            category = rel.parts[0] if len(rel.parts) > 1 else "unknown"
            entries.append({
                "id": f"comfyui:{rel}",
                "name": path.name,
                "source": "comfyui",
                "state": "available",
                "library_path": str(path),
                "category": category,
                "size_gb": bytes_gb(path.stat().st_size),
                "runtime_hints": ["comfyui"],
            })
        except OSError:
            pass
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[], help="Library base root; may be repeated")
    parser.add_argument("--include-comfyui", action="store_true", help="Include image/video/audio model artifacts")
    parser.add_argument("--output-dir", default="artifacts/inventory")
    args = parser.parse_args()

    bases = candidate_bases(args.root)
    roots_seen: list[dict] = []
    models: list[dict] = []

    for base in bases:
        base_info = {"path": str(base), "exists": base.exists()}
        roots_seen.append(base_info)
        if not base.exists():
            continue

        ollama_roots = locate(base, ["Ollama/models", "ollama/models"])
        if (base / "manifests").exists():
            ollama_roots.append(base)
        for root in dict.fromkeys(ollama_roots):
            models.extend(ollama_models(root))

        hf_roots = locate(base, ["HuggingFace", "huggingface", "HF"])
        if (base / "hub").exists() and any((base / "hub").glob("models--*")):
            hf_roots.append(base)
        for root in dict.fromkeys(hf_roots):
            models.extend(hf_models(root))

        if args.include_comfyui:
            for root in locate(base, ["ComfyUI/models", "comfyui/models"]):
                models.extend(comfy_models(root))

    # De-duplicate identical logical entries reached through overlapping roots.
    dedup: dict[str, dict] = {}
    for model in models:
        dedup.setdefault(model["id"], model)
    models = sorted(dedup.values(), key=lambda x: (x.get("source", ""), x.get("name", "")))

    summary = {
        "total": len(models),
        "by_source": {},
        "by_state": {},
    }
    for model in models:
        summary["by_source"][model["source"]] = summary["by_source"].get(model["source"], 0) + 1
        summary["by_state"][model["state"]] = summary["by_state"].get(model["state"], 0) + 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "schema_version": 1,
        "captured_at_utc": stamp,
        "inventory_kind": "cold_model_library",
        "roots": roots_seen,
        "summary": summary,
        "models": models,
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"model-library-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
