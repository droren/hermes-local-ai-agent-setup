# 009 - Hermes Bootstrap Prompt

Use the prompt below in the existing Hermes instance to inspect the real environment and prepare an **isolated secondary Hermes Next profile**.

The prompt is intentionally conservative. It must not modify the active profile during discovery.

## Bootstrap prompt

```text
You are going to prepare an experimental secondary profile named "Hermes Next" for this Hermes installation.

IMPORTANT SAFETY RULES

1. Treat my current Hermes profile, memory, skills, knowledge base, plugins, configuration and working projects as PRODUCTION DATA.
2. Do not modify, migrate, delete, rewrite, compact, re-index or overwrite any existing production data during discovery.
3. Do not change my default Hermes profile.
4. Do not change existing model registrations or endpoints.
5. Do not install software until you have produced an inventory and implementation plan for my approval.
6. Do not expose credentials, tokens, private source code or private knowledge to external models.
7. Prefer read-only inspection wherever possible.
8. Every proposed change must have a rollback method.

GOAL

Create a second, explicitly selected Hermes profile/workspace that implements a local-first multi-agent development workflow while retaining read access to the skills and useful knowledge accumulated by my existing Hermes environment.

The existing profile must remain my default and continue working exactly as it does now.

ARCHITECTURAL PRINCIPLES

- Local first.
- Open-source first.
- Reuse before creation.
- Evidence before action.
- Retrieve existing project knowledge and similar prior work before planning.
- Use capabilities rather than hard-coded model names in workflow logic.
- Prefer multiple small specialized local models over one large general model when practical.
- Break large features into bounded tasks before execution.
- Each implementation task must be independently reviewable and testable.
- Separate Planner, Implementer, Reviewer, Tester, Security Reviewer and Documenter responsibilities.
- Prefer independent agents/models for implementation and review when resources allow.
- External models are escalation capabilities, not the default orchestrator.
- Before external escalation, first attempt retrieval, decomposition and a different local specialist.
- Minimize any information sent externally.
- Every completed task should improve structured knowledge and reusable experience.
- Do not blindly append entire conversations to long-term context.

PHASE 1 - DISCOVERY ONLY

Inspect this actual Hermes installation and produce a machine-readable and human-readable inventory of:

A. Hermes
- installed Hermes version and source/installation path
- profile/workspace mechanism
- active profile
- configuration files and precedence
- plugin mechanism
- hooks
- agent/subagent capabilities
- available tool interfaces
- how system prompts/instructions are extended

B. Existing reusable assets
- skills and their locations
- knowledge/memory stores and formats
- project-specific memories
- global/user memories
- embeddings/vector stores if present
- databases used by Hermes
- reusable prompts and policies

C. Models and runtimes
- all configured local and external model providers
- Ollama endpoints and installed models
- MLX or other OpenAI-compatible local endpoints
- model context limits if discoverable
- tool-calling support
- structured-output support
- actual free memory/resource constraints on the AI host where available

D. Current integration topology
- client host versus model-server host
- SSH or remote execution paths
- Git integrations
- test/build tools
- browser/web-retrieval tools
- container runtimes

E. Isolation feasibility
Determine the safest supported method for creating a secondary Hermes profile that:
- is selected explicitly and never silently becomes default;
- has separate writable state/cache/task history/experimental memory;
- can reuse existing skills without copying or modifying them where possible;
- can retrieve existing knowledge read-only during initial testing;
- can later migrate selected learned knowledge after explicit approval.

Do not make changes in Phase 1.

PHASE 1 OUTPUT

Create an inventory report containing:

1. Current topology
2. Exact relevant paths
3. Existing profile mechanism
4. Existing skills/memory/knowledge stores
5. Model/provider inventory
6. Supported concurrency observations
7. Risks to the current installation
8. Recommended isolation design
9. Files that would be created or changed in Phase 2
10. Rollback procedure
11. Unknowns that require testing

Also create a proposed capability registry. Do not bind workflows permanently to model names. For every discovered model, characterize capabilities such as:

- routing.classify
- summarization.compact
- planning.decomposition
- architecture.reasoning
- code.implement
- code.review
- test.design
- security.review
- documentation.write
- structured_output
- tool_calling
- research.web.current
- vision.inspect
- embedding.semantic

Include observed or estimated:
- execution backend
- local/external class
- memory footprint
- useful context size
- speed class
- maximum sensible concurrency
- languages/framework strengths
- weaknesses

PHASE 2 - ONLY AFTER EXPLICIT APPROVAL

Create the isolated Hermes Next profile using the supported mechanism discovered in Phase 1.

Initial workflow:

REQUEST
  -> identify project/context
  -> retrieve existing knowledge
  -> search for similar prior work and learned patterns
  -> decide reuse/adapt/new work
  -> scope complexity
  -> decompose until tasks are locally manageable
  -> generate plan + acceptance criteria
  -> human approval
  -> capability-based local model selection
  -> implement one bounded task
  -> independent code review
  -> tests
  -> risk-based security review
  -> documentation
  -> acceptance
  -> compact project-memory update
  -> experience/pattern update

TASK SIZING

A task is too large if it cannot reasonably be implemented, independently reviewed, tested and summarized in one focused execution cycle using bounded retrieved context.

When a task is too large:
1. Do not immediately escalate externally.
2. Decompose it.
3. Re-evaluate each child task.
4. Escalate only the irreducible reasoning/research component if policy permits.

TRUST POLICY - INITIAL

- New task classes require my approval after planning and before implementation.
- Track successful executions by task class and capability.
- After three consecutive clean executions of the same task class with no blocking review findings, failed tests, scope violations or operator corrections, Hermes Next may PROPOSE a fast path.
- It must never activate the fast path itself.
- I must explicitly enable it.
- A material failure revokes or reduces trust for that class.

MEMORY POLICY

Separate memory into:
- working task context
- project knowledge
- stable operator/environment knowledge
- architecture decisions
- episodic compact summaries
- reusable workflow/pattern library
- searchable archive

Before planning, retrieve narrowly from the most relevant scopes.
Do not inject the complete long-term memory into every request.

EXPERIENCE ENGINE

Record structured outcomes including:
- task type
- decomposition pattern
- selected capabilities/models
- operator corrections
- review findings
- tests and results
- failures and fixes
- reusable procedures
- final acceptance status

Use this to improve routing, decomposition and retrieval over time. Do not claim that a base model has been trained merely because workflow experience has been stored.

PARALLELISM

Design for parallel execution when tasks are independent and resources allow it.
Do not load multiple large models merely to create superficial concurrency.
Prefer several small specialists and one larger local reasoner that can be scheduled when needed.
Resource scheduling must prevent memory pressure from destabilizing the model host.

EXTERNAL ESCALATION

External models may be used only when one or more of these are true:
- architecture/reasoning remains too difficult after decomposition;
- current web research is required and local retrieval is insufficient;
- an independent high-value second opinion is warranted.

External output is advisory and returns to the local review pipeline.
Do not automatically let an external model implement the full feature.

DELIVERABLES

Once Phase 2 is approved, create:
- isolated Hermes Next profile
- model capability catalog
- role definitions
- workflow/state definitions
- local-first execution policy
- external escalation policy
- trust policy
- read-only links/adapters to current skills and knowledge
- separate experimental memory/state
- logging/checkpointing
- a smoke-test workflow
- rollback instructions

Before changing anything, show me the Phase 1 report and the exact Phase 2 plan.
```
