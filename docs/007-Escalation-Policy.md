# 007 - External Escalation Policy

## Default

External execution is denied unless local execution has first been considered.

## Required sequence

Before escalation Hermes Next must ask:

1. Is relevant prior knowledge already available?
2. Can the task be decomposed further?
3. Can a different local specialist solve the difficult subproblem?
4. Can retrieval or a local tool provide the missing information?
5. Is current internet research genuinely required?
6. Is the information safe to disclose externally?

## Allowed external use cases

Examples:

- high-level architecture review;
- unusually complex reasoning after local decomposition fails;
- current web research not practically available locally;
- independent second opinion for high-impact design decisions.

## Data minimization

External prompts should contain the minimum information required. Source code, credentials, personal data and internal knowledge must not be included unless explicitly approved and necessary.

## Return path

External output is advisory. It returns to the local orchestration pipeline and is reviewed before implementation.
