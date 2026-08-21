# 005 - Model and Capability Registry

## Principle

Workflow definitions must depend on capabilities, not hard-coded model names.

## Capability dimensions

A model registration may advertise:

- coding languages;
- code generation;
- code review;
- test generation;
- reasoning depth;
- structured output reliability;
- long-context retrieval;
- vision;
- embeddings;
- web research;
- tool calling;
- latency class;
- memory footprint;
- maximum safe concurrency;
- privacy class;
- local/external execution class.

## Selection order

The orchestrator should select:

1. a local model already resident in memory when capable;
2. another local model that can be loaded within resource policy;
3. decomposition or a smaller specialized model combination;
4. an external model only if the escalation policy permits it.

## Continuous evaluation

Model rankings are local and empirical. Benchmark scores are useful hints, but successful execution history on the operator's own workload has higher weight.
