# Standalone Orchestrator Prototype

This prototype validates the Hermes Next workflow before integrating it into the user's active Hermes installation.

## Purpose

The orchestrator implements the first end-to-end local flow:

1. search existing local project knowledge first;
2. route and classify the request with `qwen3:1.7b`;
3. decompose medium/large work into bounded subtasks when needed;
4. ask `granite3.3:2b` for a proposed implementation artifact;
5. ask `ministral-3:3b` to independently test/review that artifact;
6. apply a verification gate;
7. write a complete JSON run log.

The prototype is intentionally **read-only**. It does not apply patches, execute generated code, mutate repositories, stage models, or call external providers.

## Quick start

From the repository root:

```bash
python3 orchestrator/run_orchestrator.py \
  "Add validation so a discount outside 0..100 is rejected, preserve current API output, and add boundary tests."
```

By default it searches these repository paths before inference:

```text
docs/
knowledge/
experience/
config/
```

Add project-specific knowledge roots with repeated flags:

```bash
python3 orchestrator/run_orchestrator.py \
  --knowledge-root /path/to/project/docs \
  --knowledge-root /path/to/project \
  "Move freight calculation behind ShippingService and add regression tests."
```

Or provide a task file:

```bash
python3 orchestrator/run_orchestrator.py \
  --task-file examples/task.txt
```

## Expected output

The command prints a short summary:

```text
status: verified_proposal
subtasks: 2
verified: 2/2
wall_seconds: ...
artifacts/orchestrator-runs/orchestrator-run-....json
```

The JSON log includes:

- retrieved knowledge hits;
- routing decision;
- decomposition result;
- worker artifact for every subtask;
- independent tester evaluation;
- verification-gate result;
- model names and timing;
- an explicit safety record showing that nothing was applied or executed.

## Important current limitation

Retrieval is intentionally a small lexical baseline. It proves the workflow rule **retrieve before inference**, but it is not the final Hermes memory architecture. The next retrieval implementation should combine existing Hermes knowledge/memory with a persistent structured/vector store and experience records.

Likewise, the worker currently produces a **proposed change description**, not an actual patch. That is deliberate. The next trust level should add a temporary worktree/sandbox where a worker may generate a patch, run tests, receive independent review, and only then request human approval to apply the result.

## External escalation

If the router says that current web information is materially required, the prototype stops with:

```text
external_escalation_recommended
```

It does not silently call an external provider. The later Hermes integration will apply the project's external-escalation policy and send only the minimum necessary context.
