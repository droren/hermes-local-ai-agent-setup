# ADR-0001: Local-first capability routing

Status: Accepted

## Context

A model-name-driven architecture becomes brittle as models improve and local resources change.

## Decision

Agents request capabilities. The orchestrator resolves those capabilities against a model registry and prefers local execution.

## Consequences

Models can be replaced without rewriting workflows. Registry quality and local benchmarking become important parts of system maintenance.
