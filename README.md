# Hermes Next Development Kit

Hermes Next is a local-first, open-source-first architecture for orchestrating specialized AI agents for software development and knowledge-intensive workflows.

The project is designed around one principle: **use the smallest capable local model for the job, reuse existing knowledge before generating new work, and escalate externally only when decomposition and local execution are insufficient.**

## Status

Version: `0.1.0-alpha`

This repository currently contains the architecture, policies, workflow definitions, agent contracts, capability registry format, experience-learning design and a safe bootstrap layout for a secondary Hermes profile.

It is deliberately separated from an existing production Hermes profile.

## Core principles

- Local first
- Open source first
- Reuse before creation
- Evidence before action
- Capability-driven model selection
- Small, verifiable tasks
- Independent review and testing
- Human approval by default, with earned trust over time
- Knowledge compounding
- External models as an escalation path, not the default
- Reproducible and replaceable components

## Repository layout

```text
.
├── README.md
├── ROADMAP.md
├── CONTRIBUTING.md
├── LICENSE
├── docs/
│   ├── 000-Vision.md
│   ├── 001-Architecture.md
│   ├── 002-System-Workflow.md
│   ├── 003-Agent-Model.md
│   ├── 004-Knowledge-Memory.md
│   ├── 005-Model-Capabilities.md
│   ├── 006-Experience-Engine.md
│   ├── 007-Escalation-Policy.md
│   ├── 008-Migration-and-Profile-Isolation.md
│   └── adr/
├── config/
│   ├── hermes-next.example.yaml
│   └── model-catalog.example.yaml
├── agents/
│   └── roles.yaml
├── policies/
│   ├── execution-policy.yaml
│   └── trust-policy.yaml
├── workflows/
│   └── feature-lifecycle.yaml
├── knowledge/
│   └── README.md
├── experience/
│   └── README.md
├── bootstrap/
│   └── bootstrap-hermes-next.sh
├── examples/
│   └── feature-request.yaml
└── benchmarks/
    └── README.md
```

## Intended execution model

```text
User request
    |
    v
Hermes Next Orchestrator
    |
    +--> Knowledge / prior-work retrieval
    |        |
    |        +--> reuse / adapt / pattern match
    |
    +--> Scope and complexity gate
    |        |
    |        +--> decompose until locally executable
    |
    +--> Capability matching
    |        |
    |        +--> local agent + local model
    |        +--> external escalation only by policy
    |
    +--> Implement -> Review -> Test -> Security -> Document
    |
    +--> Human approval / trust policy
    |
    +--> Knowledge + Experience update
```

## Safety of the experimental profile

The bootstrap script creates a separate profile directory and refuses to overwrite an existing path unless explicitly changed by the operator. Existing Hermes skills and knowledge should be referenced read-only or through explicitly configured shared paths during early testing.

Do not point the experimental profile at writable production memory until the migration design has been tested.

## Next milestone

The next implementation milestone is to map this generic architecture onto the exact Hermes version, configuration format, installed skill layout, memory implementation and local model endpoints in the target environment.
