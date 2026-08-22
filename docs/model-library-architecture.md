# Model Library Architecture

Hermes Next treats model ownership, local staging, runtime registration, and active serving as separate concerns.

## States

### cold_available
The model artifact exists in the durable shared model library on UNAS/NAS storage. It is known to Hermes, but it MUST NOT be executed directly from network storage.

### staged_local
A complete runnable copy of the model exists on the AI host's local SSD. It may not yet be registered with a runtime, but it is eligible for local activation.

### activatable_local
The model is staged on local SSD and Hermes has enough metadata to identify a supported runtime activation path.

### registered
The local runtime knows about the staged model, for example through an Ollama manifest or configured MLX model slot, but the model is not necessarily resident in unified memory.

### active
The model is currently serving or resident/loaded through a runtime on the host.

### available_incomplete
A manifest/cache/catalog entry exists but one or more required artifacts appear to be missing.

## Storage tiers

### Tier 1 - Durable cold library (UNAS Pro)

Preferred location: the UNAS Pro shared model volume.

Current mount naming supported by inventory tooling:
- `/Volumes/Shared_ModelDrive/ModelDrive`
- legacy `/Volumes/ModelStore`

This is the durable source of truth for model artifacts and avoids repeated Internet downloads. It is **not an inference tier**.

Network storage latency and throughput make loading multi-gigabyte model weights directly from the UNAS unsuitable for interactive model switching. Hermes MUST therefore never schedule inference directly against an artifact whose only state is `cold_available`.

### Tier 2 - Local SSD model cache/staging area

The Mac Mini Pro's local SSD is the required execution source for model weights. Models selected from the cold library must first be copied/staged to the configured local model-cache path.

This tier should be capacity-managed rather than treated as a permanent mirror of the UNAS library. Frequently used models can remain staged; infrequently used models may be evicted only after policy checks confirm that the durable library contains a verified copy.

### Tier 3 - Runtime/active memory

Ollama, MLX, or another backend registers a model from the local SSD. The model may then be loaded into unified memory when an agent requires its capability.

Absence from this tier does not mean that Hermes does not own the model; it means activation may require local staging and runtime registration first.

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

`scripts/inventory-host.sh` answers: **what is locally registered/available to this host right now?**

`scripts/inventory-model-library.py` answers: **what model artifacts do we already own in durable cold storage?**

A future local-cache inventory answers: **what models are already staged on fast local SSD even if not currently registered or active?**

The capability catalog combines all three views with benchmark results.

## Model-selection lifecycle

When Hermes selects a capability, selection follows this order:

1. Find the best acceptable `active` or `registered` local model.
2. If none exists, find the best `activatable_local` or `staged_local` model.
3. If none exists, search `cold_available` models in the UNAS library.
4. If a cold model is selected, calculate required local disk space and stage/copy it to the Mac Mini Pro SSD.
5. Verify the staged copy before use.
6. Register/activate it in the appropriate local runtime.
7. Run the task locally.
8. Keep or evict the staged copy according to cache policy and expected reuse.
9. Only consider a new Internet download when no acceptable owned model exists.

This means model switching can have two very different costs:

- **warm switch**: model already staged locally; only runtime load/registration cost;
- **cold switch**: model must first be transferred from UNAS to local SSD, which may take significant time.

Hermes scheduling and planning MUST account for that staging cost. A marginally better cold model should not automatically displace a slightly lower-ranked model that is already staged locally.

## Activation and staging policy

Inventory is deliberately read-only. It must not:
- download models;
- copy models from UNAS to local SSD;
- rewrite Ollama manifests;
- start model servers;
- delete or deduplicate artifacts.

Staging/activation is a separate explicit operation with checks for:
- available local SSD capacity;
- source completeness;
- copy integrity/checksum when available;
- expected transfer size/time;
- RAM/context requirements;
- backend compatibility;
- benchmark evidence;
- whether another staged model may safely be evicted.

Until trust policy is expanded, automatic eviction or replacement of locally staged models should require human approval.
