# 004 - Knowledge and Memory Architecture

## Problem

Unbounded conversational memory eventually becomes expensive, noisy and counterproductive. Hermes Next therefore separates memory by purpose and retrieves information on demand.

## Memory tiers

### Working memory

Current task state only. Short-lived and aggressively bounded.

### Project memory

Architecture, conventions, important code locations, active decisions and project-specific patterns.

### Stable operator knowledge

Long-lived preferences, environment conventions and workflows that are broadly reusable.

### Episodic memory

Compact summaries of completed work sessions, preserving decisions and outcomes rather than raw transcripts.

### Pattern library

Reusable procedures learned from repeated successful workflows.

Examples include how a specific team writes product descriptions, how a deployment is normally performed, or how a particular project structures tests.

### Archive

Raw historical material that is searchable but never automatically injected.

## Retrieval policy

Before planning, the orchestrator should query in this order:

1. active project facts;
2. architecture and ADRs;
3. similar prior tasks;
4. pattern library;
5. operator preferences;
6. archive only when needed.

## Compression

Memory compaction should preserve:

- decisions;
- rationale;
- verified facts;
- artifact references;
- failures and fixes;
- reusable procedures;
- unresolved questions.

Conversational filler and superseded intermediate reasoning should be discarded.
