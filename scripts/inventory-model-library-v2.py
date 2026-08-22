#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

EXTS = {'.safetensors', '.gguf', '.ckpt', '.pth', '.pt'}


def gb(n: int) -> float:
    return round(n / 1024**3, 3)


def dsize(root: Path) -> int:
    total = 0
    for base, _, files in os.walk(root):
        for name in files:
            try:
                total += (Path(base) / name).stat().st_size
            except OSError:
                pass
    return total


def parse_ollama_manifest(manifests: Path, blobs: Path, mf: Path, store_name: str) -> dict:
    rel = mf.relative_to(manifests)
    p = rel.parts
    try:
        reg_idx = next(i for i, part in enumerate(p) if part.startswith('registry.'))
    except StopIteration:
        reg_idx = 0

    q = p[reg_idx:]
    if len(q) < 4:
        raise ValueError(f'unrecognized Ollama manifest path: {rel}')

    registry, namespace = q[0], q[1]
    tag = q[-1]
    model = '/'.join(q[2:-1])
    name = f'{namespace}/{model}:{tag}' if namespace != 'library' else f'{model}:{tag}'

    data = json.loads(mf.read_text())
    raw_layers = data.get('layers')
    layers = raw_layers if isinstance(raw_layers, list) else []
    raw_cfg = data.get('config')
    cfg = raw_cfg if isinstance(raw_cfg, dict) else {}

    refs = [x.get('digest') for x in [cfg, *layers] if isinstance(x, dict) and x.get('digest')]
    missing = [d for d in refs if not (blobs / d.replace(':', '-')).exists()] if blobs.exists() else refs
    size = sum(int(x.get('size', 0) or 0) for x in [cfg, *layers] if isinstance(x, dict))

    # Cloud-only manifests often contain no local layers/config. Keep them as metadata,
    # but do not treat them as stageable local models.
    cloud_only = tag == 'cloud' or tag.endswith('-cloud') or (not refs and size == 0)
    state = 'external_reference' if cloud_only else ('cold_available' if not missing else 'available_incomplete')

    return {
        'id': f'ollama:{name}',
        'name': name,
        'source': 'ollama',
        'state': state,
        'locations': [{
            'store': store_name,
            'manifest_path': str(mf),
            'blob_root': str(blobs),
            'complete': (not cloud_only and len(missing) == 0),
            'missing_blob_count': len(missing),
        }],
        'declared_size_gb': gb(size),
        'runtime_hints': ['ollama'],
        'requires_local_staging': not cloud_only,
    }


def discover_ollama_stores(root: Path) -> list[tuple[str, Path, Path]]:
    out: list[tuple[str, Path, Path]] = []
    if not root.exists():
        return out

    candidates: list[Path] = []
    if (root / 'manifests').exists():
        candidates.append(root)
    stores = root / 'stores'
    if stores.exists():
        for p in stores.iterdir():
            if p.is_dir() and (p / 'manifests').exists():
                candidates.append(p)
    for manifests in root.glob('**/manifests'):
        parent = manifests.parent
        if parent not in candidates:
            candidates.append(parent)

    seen: set[str] = set()
    for store in candidates:
        key = str(store)
        if key in seen:
            continue
        seen.add(key)
        out.append((store.name, store / 'manifests', store / 'blobs'))
    return out


def ollama(root: Path) -> list[dict]:
    out: list[dict] = []
    for store_name, manifests, blobs in discover_ollama_stores(root):
        for mf in manifests.rglob('*'):
            if not mf.is_file():
                continue
            try:
                out.append(parse_ollama_manifest(manifests, blobs, mf, store_name))
            except Exception as e:
                out.append({
                    'id': f'ollama-manifest:{mf}',
                    'name': mf.name,
                    'source': 'ollama',
                    'state': 'inventory_error',
                    'locations': [{'store': store_name, 'manifest_path': str(mf)}],
                    'error': str(e),
                    'requires_local_staging': True,
                })
    return out


def hf(root: Path) -> list[dict]:
    out = []
    hub = root / 'hub' if (root / 'hub').exists() else root
    if not hub.exists():
        return out
    for md in sorted(hub.glob('models--*')):
        if not md.is_dir():
            continue
        repo = md.name[len('models--'):].replace('--', '/')
        snaps = md / 'snapshots'
        ids = [p.name for p in snaps.iterdir() if p.is_dir()] if snaps.exists() else []
        size = dsize(md)
        hints = ['transformers']
        if 'mlx' in repo.lower():
            hints.insert(0, 'mlx')
        out.append({
            'id': f'huggingface:{repo}',
            'name': repo,
            'source': 'huggingface',
            'state': 'cold_available' if ids and size else 'available_incomplete',
            'locations': [{'library_path': str(md), 'complete': bool(ids and size)}],
            'size_gb': gb(size),
            'snapshots': ids,
            'runtime_hints': hints,
            'requires_local_staging': True,
        })
    return out


def generic(root: Path, source: str) -> list[dict]:
    out = []
    if not root.exists():
        return out
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in EXTS or '/.cache/' in str(p):
            continue
        try:
            out.append({
                'id': f'{source}:{p.relative_to(root)}',
                'name': p.name,
                'source': source,
                'state': 'cold_available',
                'locations': [{'library_path': str(p), 'complete': True}],
                'size_gb': gb(p.stat().st_size),
                'runtime_hints': [source],
                'requires_local_staging': True,
            })
        except OSError:
            pass
    return out


def merge_logical_models(models: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    rank = {'inventory_error': 0, 'available_incomplete': 1, 'external_reference': 2, 'cold_available': 3}
    for m in models:
        key = m['id']
        if key not in merged:
            merged[key] = m
            continue
        current = merged[key]
        current.setdefault('locations', []).extend(m.get('locations', []))
        if rank.get(m.get('state'), -1) > rank.get(current.get('state'), -1):
            current['state'] = m.get('state')
        if 'declared_size_gb' in m:
            current['declared_size_gb'] = max(current.get('declared_size_gb', 0) or 0, m.get('declared_size_gb', 0) or 0)
        if 'size_gb' in m:
            current['size_gb'] = max(current.get('size_gb', 0) or 0, m.get('size_gb', 0) or 0)
        current['requires_local_staging'] = current.get('state') != 'external_reference'
    return sorted(merged.values(), key=lambda x: (x['source'], x['name']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/Volumes/Shared_ModelDrive/ModelDrive')
    ap.add_argument('--include-comfyui', action='store_true')
    ap.add_argument('--output-dir', default='artifacts/inventory')
    a = ap.parse_args()

    base = Path(a.root).expanduser()
    lib = base / 'library' if (base / 'library').exists() else base
    roots = {
        'ollama': lib / 'ollama',
        'huggingface': lib / 'huggingface',
        'mlx': lib / 'mlx',
        'gguf': lib / 'gguf',
        'safetensors': lib / 'safetensors',
        'comfyui': lib / 'comfyui',
    }

    models = []
    models += ollama(roots['ollama'])
    models += hf(roots['huggingface'])
    models += generic(roots['mlx'], 'mlx')
    models += generic(roots['gguf'], 'gguf')
    models += generic(roots['safetensors'], 'safetensors')
    if a.include_comfyui:
        models += generic(roots['comfyui'], 'comfyui')

    models = merge_logical_models(models)
    bys, byt = {}, {}
    for m in models:
        bys[m['source']] = bys.get(m['source'], 0) + 1
        byt[m['state']] = byt.get(m['state'], 0) + 1

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload = {
        'schema_version': 4,
        'captured_at_utc': stamp,
        'inventory_kind': 'cold_model_library',
        'execution_policy': 'stage_to_local_ssd_before_activation',
        'identity_policy': 'logical_model_separate_from_physical_locations',
        'root': str(base),
        'library_root': str(lib),
        'discovered_roots': {k: {'path': str(v), 'exists': v.exists()} for k, v in roots.items()},
        'summary': {'total': len(models), 'by_source': bys, 'by_state': byt},
        'models': models,
    }

    outdir = Path(a.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f'model-library-v4-{stamp}.json'
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    print(out)


if __name__ == '__main__':
    main()
