# Model Library Architecture

Hermes Next treats model availability separately from runtime activation.

## States

### active
The model is currently registered/exposed by a runtime on a host, for example `ollama list`.

### available
The artifact exists in the durable shared model library but may not yet have enough runtime metadata to activate automatically.

### activatable
The artifact exists in the shared library and the inventory has enough information to identify a supported activation path.

### available_incomplete
A manifest/cache entry exists but required artifacts appear to be missing.

## Storage tiers

### Durable/cold library
Preferred location: the UNAS Pro shared model volume.

Current mount naming supported by inventory tooling:
- `/Volumes/Shared_ModelDrive/ModelDrive`
- legacy `/Volumes/ModelStore`

This is the source of truth for model artifacts. Large models should not be duplicated onto each Mac merely so they appear in an inventory.

### Hot/runtime tier
Local or attached fast storage used for models currently serving requests. A model being absent from this tier does **not** mean Hermes considers it unavailable.

## Discovery

Run:

```bash
python3 scripts/inventory-model-library.py
```

To include ComfyUI artifacts as well:

```bash
python3 scripts/inventory-model-library.py --include-comfyui
```

Or explicitly select one or more roots:

```bash
python3 scripts/inventory-model-library.py \
  --root /Volumes/Shared_ModelDrive/ModelDrive
```

The environment variable `HERMES_MODEL_LIBRARY_ROOTS` may contain multiple roots separated by the platform path separator.

## Relationship to host inventory

`scripts/inventory-host.sh` answers: **what can this host serve right now?**

`scripts/inventory-model-library.py` answers: **what model artifacts do we already own locally and could potentially activate?**

The future capability catalog combines these views with benchmark results. Model selection should therefore not be constrained to the current output of `ollama list`.

## Activation policy

Inventory is deliberately read-only. It must not:
- download models;
- copy hundreds of GB to local SSD;
- rewrite Ollama manifests;
- start model servers;
- delete or deduplicate artifacts.

Activation should be a separate explicit operation with disk-space, RAM/context, backend compatibility, and benchmark policy checks.
