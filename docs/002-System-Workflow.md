# 002 - System Workflow

## Feature lifecycle

Every non-trivial feature request follows this lifecycle:

1. Intake
2. Context identification
3. Knowledge retrieval
4. Similar-work and pattern detection
5. Reuse/adapt decision
6. Scope assessment
7. Decomposition
8. Plan generation
9. Human approval when required
10. Capability matching
11. Implementation
12. Independent review
13. Testing
14. Security review where applicable
15. Documentation
16. Final acceptance
17. Knowledge update
18. Experience update

## State model

```text
NEW
 |
 v
RETRIEVING_CONTEXT
 |
 v
SCOPING
 |---- too large ----> DECOMPOSING ----+
 |                                      |
 +--------------------------------------+
 |
 v
PLANNED
 |
 +---- approval required ---> WAITING_FOR_APPROVAL
 |                              |
 +------------------------------+
 |
 v
READY
 |
 v
IMPLEMENTING
 |
 v
REVIEWING
 |---- changes requested ---> IMPLEMENTING
 |
 v
TESTING
 |---- failed -------------> IMPLEMENTING
 |
 v
SECURITY_REVIEW
 |
 v
DOCUMENTING
 |
 v
ACCEPTANCE
 |
 v
COMPLETED
 |
 +--> KNOWLEDGE_UPDATE
 +--> EXPERIENCE_UPDATE
```

## Task sizing rule

A task should be decomposed when it cannot reasonably be:

- understood with bounded retrieved context;
- implemented in one focused execution cycle;
- reviewed independently;
- tested with explicit acceptance criteria;
- summarized without losing important decisions.

Token count may be used as a signal, but it must not be the only sizing criterion.

## Checkpointing

Every stage produces persisted metadata sufficient to resume after interruption. A checkpoint should contain:

- task identifier;
- input evidence;
- selected agent role and capability;
- model/backend used;
- artifacts changed;
- commands executed;
- test output references;
- review findings;
- pending decisions;
- next permitted transition.
