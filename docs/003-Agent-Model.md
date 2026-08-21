# 003 - Agent Model

## Planner

**Goal:** convert a request into bounded, verifiable work.

Input: request, retrieved context, constraints, relevant patterns.

Output: task graph, dependencies, acceptance criteria, risk classification, required capabilities.

The Planner must prefer decomposition over external escalation.

## Implementer

**Goal:** perform one bounded implementation task.

The Implementer may not silently expand scope. Newly discovered work must be returned to the orchestrator.

## Reviewer

**Goal:** independently challenge the implementation.

The Reviewer checks correctness, maintainability, scope compliance, regressions, style and acceptance criteria. It should not assume the Implementer is correct.

## Tester

**Goal:** prove behavior, not merely create tests.

The Tester selects or generates appropriate unit, integration, regression and negative tests and records evidence.

## Security Reviewer

**Goal:** identify material security risks introduced or exposed by the change.

Security review depth is risk-based.

## Documenter

**Goal:** update human-facing documentation and produce a compact machine-retrievable completion summary.

The Documenter records what changed, why, relevant decisions, limitations and reusable lessons.

## Agent contract

Every role returns structured status:

- `success`
- `needs_changes`
- `blocked`
- `needs_decomposition`
- `needs_human_decision`
- `needs_external_capability`

No role may directly grant itself additional privileges.
