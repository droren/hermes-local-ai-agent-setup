# 000 - Vision and Design Goals

## Purpose

Hermes Next is an open, local-first orchestration design for a personal AI development team composed of multiple specialized agents and replaceable models.

The system is not optimized for running the largest possible model. It is optimized for completing useful work reliably with the smallest capable local resources, while preserving access to stronger external reasoning or research capabilities when genuinely necessary.

## Design goals

### Local first

Local models are the default execution path. External models are an exception governed by policy.

### Open source first

Core orchestration, storage, retrieval, agent definitions, model runners and workflow components should favor open implementations without mandatory paid API dependencies.

### Reuse before creation

Before planning new work, Hermes Next must search existing knowledge, project history, prior implementations, decisions, reusable code and learned workflows.

### Evidence before action

The orchestrator should collect enough evidence to justify a change before creating or modifying artifacts.

### Capability-driven execution

Agents request capabilities, not model names. Model selection is performed through a registry that maps tasks to available capabilities, cost, latency, context budget and resource requirements.

### Small, verifiable tasks

Large features are decomposed until each task can be implemented, reviewed, tested and documented within a bounded context and execution cycle.

### Independent verification

Implementation, review and testing should normally be performed by separate agent roles. A model must not be trusted merely because it produced syntactically valid output.

### Human authority

The operator remains the final authority for consequential changes. Automation privileges are earned gradually through successful execution history.

### Knowledge compounding

Every completed task should leave the system better informed than before through structured summaries, decisions, reusable patterns, test evidence and outcome metadata.

### Replaceability

Models, tools and storage engines must be replaceable without redesigning the workflow.

### Privacy by architecture

Private source code, credentials, internal knowledge and unnecessary project data should not be sent to external services.

### Reproducibility

A second machine should be able to recreate the orchestration setup from version-controlled configuration while preserving user-specific secrets and private knowledge separately.
