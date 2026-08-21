# 001 - Architecture

## Overview

Hermes Next treats Hermes as an orchestration layer for a team of specialized agents rather than as a single all-purpose assistant.

The architecture is composed of six logical layers.

```text
+-------------------------------------------------------------+
|                         USER / CLIENT                       |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                  HERMES NEXT ORCHESTRATOR                   |
| scope | routing | policy | approvals | state | task graph   |
+----------+------------------+------------------+-------------+
           |                  |                  |
           v                  v                  v
+----------------+   +----------------+   +-------------------+
| KNOWLEDGE &    |   | POLICY & TRUST |   | CAPABILITY /      |
| MEMORY         |   | ENGINE         |   | MODEL REGISTRY    |
| RAG / history  |   | gates / risk   |   | local + external  |
+--------+-------+   +--------+-------+   +---------+---------+
         |                    |                     |
         +--------------------+---------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      SPECIALIZED AGENTS                     |
| planner | implementer | reviewer | tester | security | docs |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                       TOOL EXECUTION                        |
| git | filesystem | tests | containers | ssh | web | CI/CD  |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 EXPERIENCE / KNOWLEDGE UPDATE               |
| outcomes | patterns | confidence | reusable procedures      |
+-------------------------------------------------------------+
```

## 1. Orchestration layer

The orchestrator owns task state and is responsible for:

- identifying project and task context;
- retrieving prior knowledge before planning;
- estimating scope and complexity;
- decomposing oversized work;
- selecting agent capabilities;
- applying local-first and escalation policies;
- enforcing quality gates;
- requesting human approval where required;
- recording results and evidence.

The orchestrator should avoid doing implementation work itself when a specialized role is available.

## 2. Knowledge and memory layer

Knowledge is divided into bounded scopes rather than continuously injected global memory.

Recommended scopes:

- stable operator preferences and environment facts;
- project knowledge;
- architectural decisions;
- active task working context;
- reusable implementation patterns;
- episodic summaries;
- archival raw history.

Retrieval is mandatory before new planning.

## 3. Policy and trust layer

The policy engine controls:

- whether a task may run autonomously;
- whether an external model may be used;
- which tools an agent may invoke;
- whether writes require approval;
- whether a task qualifies for a learned fast path.

Trust is earned per task class and capability, never globally.

## 4. Capability and model registry

Agent definitions request capabilities such as:

- `code.php.review`
- `code.python.implement`
- `architecture.reasoning`
- `test.unit.generate`
- `research.web.current`
- `vision.ui.inspect`
- `embedding.semantic`

The registry maps those capabilities to currently available models and execution backends.

## 5. Specialized agent layer

Initial roles:

- Planner
- Implementer
- Reviewer
- Tester
- Security Reviewer
- Documenter

Additional roles may be introduced without changing the lifecycle contract.

## 6. Tool execution layer

Tools are isolated from models through explicit permissions. Examples include Git, local filesystems, test frameworks, container runtimes, SSH, web retrieval and CI systems.

## 7. Experience engine

The Experience Engine observes successful and failed workflows and stores structured evidence about:

- which decomposition worked;
- which model performed well for which capability;
- recurring operator corrections;
- common failure modes;
- useful tool sequences;
- reusable product or content-entry patterns.

It does not blindly train models. Its primary job is to improve retrieval, routing and procedure selection.
