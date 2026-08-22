# 010 - Local Model Strategy

Status: Draft v0.2

## Goal

Hermes Next should maximize useful local execution rather than maximize model size. The target is a local AI development team where several bounded specialist jobs can proceed concurrently on a 48 GB Apple Silicon host, while stronger local and external models remain escalation tiers.

## Design rule

**Capability first, model second.**

Agents request capabilities such as `code.review.deep`, `test.design`, or `routing.classify`. The model catalog decides which currently installed model supplies that capability. Agent prompts and workflows must not depend on a concrete model name.

## Execution tiers

### Tier 0 - Retrieval before inference

Before assigning substantial inference work, query project knowledge, prior decisions, patterns, reusable implementations, and experience records. A task that can be answered by retrieval plus a small model should not wake a large model.

### Tier 1 - Utility agents

Small models handle classification, summaries, metadata extraction, task routing, documentation transforms, and other bounded operations. They should be cheap enough to remain resident or be started frequently.

### Tier 2 - Local workers

Small-to-medium models implement narrowly scoped changes, generate tests, inspect repositories, update documentation, and perform first-pass review. This tier should perform most day-to-day work.

### Tier 3 - Local senior worker

A stronger local model handles difficult implementation, decomposition, and review when Tier 2 is insufficient. A sparse/MoE model is preferred when it provides strong quality while preserving memory and throughput for supporting agents.

### Tier 4 - Local quality reserve

A larger dense local model may be used for difficult architecture/review/reasoning jobs. It is deliberately not the default because consuming most unified memory for one agent works against the parallel-team design.

### Tier 5 - External escalation

Existing Hermes external providers are a capability of last resort, not the orchestrator. External use is appropriate when:

1. current web research materially affects correctness;
2. decomposition has failed to make a problem locally tractable;
3. local review repeatedly fails a quality gate;
4. architecture risk justifies an independent stronger opinion.

External requests should receive the minimum context required for the question. Implementation should return to local agents whenever practical.

## 48 GB memory policy

Treat unified memory as a shared scheduling resource. Do not plan for 48 GB of model weights: macOS, inference runtimes, KV caches, tools, and concurrent agents need headroom.

Initial scheduling target:

- reserve about 10 GB for OS/runtime/headroom;
- target about 38 GB maximum aggregate model/runtime budget;
- prefer multiple small workers over multiple large models;
- never load two large dense models merely to simulate different agent roles;
- agent identity is a prompt/policy concern and does not require a unique model process.

These values are starting assumptions and MUST be replaced by measured peak memory on the actual host.

## Parallel operating profiles

### Normal

Router + two bounded local worker jobs. Intended for independent subtasks such as implementation, tests, documentation, or repository analysis.

### Mixed review

One stronger MoE coding/reasoning worker plus lightweight routing/retrieval support. Intended for implementation followed by independent small-agent test/document preparation.

### Deep local

One high-quality dense model plus lightweight routing. Parallelism is intentionally reduced. Use only when benchmarks show a material quality advantage.

## Independent review requirement

The reviewer role should not blindly inherit the implementer's context. It receives:

- task specification;
- acceptance criteria;
- resulting diff/artifacts;
- relevant retrieved project rules;
- test evidence.

Where memory allows, review SHOULD use a different model class or at minimum a fresh inference context. This reduces agreement-by-context rather than pretending two prompts against the same conversation are independent reviewers.

## Benchmark before promotion

A model is not promoted because a leaderboard says it is good. Each capability has a local benchmark set derived from real work. Record:

- success/failure;
- wall-clock time;
- peak unified memory;
- tokens/context consumed;
- tool-call correctness;
- review defects found;
- test pass rate;
- human corrections required.

The Experience Engine may recommend changing capability mappings when enough evidence accumulates, but must not silently rewrite production policy.

## Initial candidate mapping

The accompanying `config/model-catalog.example.yaml` contains an initial candidate mapping for routing, bounded work, stronger MoE coding, dense quality reserve, embeddings, and external escalation. Concrete model identifiers are replaceable defaults and should be validated against what Ollama/MLX actually exposes on the target host.

## Next implementation step

Build a host inventory and benchmark command that records installed models, runtime/backend, quantization, measured memory, latency, context limit, and capability scores. Hermes should generate a host-specific catalog from those measurements rather than relying permanently on this example file.
