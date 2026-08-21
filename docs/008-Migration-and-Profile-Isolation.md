# 008 - Migration and Profile Isolation

## Objective

Hermes Next must be testable without damaging or silently mutating the operator's established Hermes profile.

## Rules

1. Create a separate profile/workspace directory.
2. Do not overwrite existing configuration.
3. Share existing skills through references or explicit read-only paths where possible.
4. Share knowledge initially through read-only retrieval.
5. Use a separate experimental state, task database, caches and writeable memory.
6. Migrate learned state only after explicit review.
7. Keep a rollback path at all times.

## Suggested layout

```text
~/.hermes/                  # existing production installation/profile
~/.hermes-next/             # isolated experimental profile
~/ai/hermes-shared/         # optional shared read-only resources
```

The exact paths and Hermes configuration mechanism must be validated against the installed Hermes version before bootstrap automation is enabled.
