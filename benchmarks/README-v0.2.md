# Benchmark Harness v0.2

This harness measures models on the actual Hermes Next host rather than promoting models from public leaderboards alone.

## 1. Inventory the AI host

From the repository root on the Mac running Ollama/MLX:

```bash
chmod +x scripts/inventory-host.sh
./scripts/inventory-host.sh
```

The script writes a timestamped JSON file under `artifacts/inventory/` containing Apple hardware, unified memory, runtime versions, and locally installed Ollama models. It does not install or modify models.

## 2. Run a capability benchmark

```bash
python3 benchmarks/benchmark-model.py \
  --model YOUR_MODEL \
  --capability routing.classify \
  --prompt-file benchmarks/prompts/routing-classify.md \
  --endpoint http://127.0.0.1:11434
```

For a remote AI host, point `--endpoint` to its Ollama endpoint.

Code review example:

```bash
python3 benchmarks/benchmark-model.py \
  --model YOUR_MODEL \
  --capability code.review \
  --prompt-file benchmarks/prompts/code-review-small.md \
  --endpoint http://127.0.0.1:11434
```

Results are written to `artifacts/benchmarks/` as JSON.

## What is measured now

- wall-clock duration;
- model load duration reported by Ollama;
- prompt token count and prompt-evaluation duration;
- output token count and generation duration;
- generation tokens/second;
- approximate macOS memory snapshots before and after;
- raw response;
- placeholders for human score/corrections/acceptance.

## Important limitation

A before/after `vm_stat` snapshot is not a reliable per-process peak-memory measurement. It is intentionally labelled approximate. A later iteration should sample process/system memory during generation and record a peak delta. Do not optimize scheduling from this field alone.

## Benchmark philosophy

A benchmark case should correspond to a Hermes capability and resemble real work. The long-term suite should contain multiple cases for each capability and deterministic validators where possible.

Recommended first capability suite:

1. `routing.classify`
2. `summarization.compact`
3. `planning.decomposition`
4. `structured_output`
5. `tool_calling`
6. `code.implement.small`
7. `code.review`
8. `test.design`

## Safety

Benchmarking must not mutate production repositories. Code-writing cases should operate on fixtures or temporary worktrees/containers. Promotion to a production capability mapping remains a human-approved policy change.
