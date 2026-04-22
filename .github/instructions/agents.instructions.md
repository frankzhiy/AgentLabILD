---
applyTo: "src/agents/**/*.py,configs/prompts/**/*.md"
---

# Agent and Prompt Instructions

When editing agent code or prompt templates in this repository:

## 1) Agent role

Agents are adapters into system mechanisms.

They may generate:
- structured extraction
- structured hypothesis candidates
- structured conflict candidates
- structured update proposals

They should not silently define platform rules.

## 2) Responsibility boundaries

Keep responsibilities narrow.

Examples:

- `Case Structurer`:
  - allowed: normalize case structure, build timeline, extract structured fields
  - not allowed: final diagnosis, arbitration, safety override

- `Evidence Atomizer`:
  - allowed: extract evidence atoms, polarity, certainty, temporality, source spans
  - not allowed: hidden diagnosis synthesis

- `Hypothesis State Agent`:
  - allowed: produce candidate hypothesis state objects
  - not allowed: bypass top-k preservation or validation rules

- `Conflict Agent`:
  - allowed: identify and type conflicts
  - not allowed: add or remove evidence

- `Arbiter`:
  - allowed: synthesize according to external rules
  - not allowed: ignore safety gate or unresolved high-risk conflicts

## 3) Prompt rule

Prompt instructions are helpers, not guarantees.

Do not rely on prompt wording alone for:

- evidence grounding
- safety
- schema integrity
- conflict escalation
- local revision correctness

If such behavior is required, implement an external mechanism or validator.

## 4) Output rule

Prefer structured outputs over prose.

If an agent produces free-text commentary, make sure authoritative state is still captured in structured objects.

Free-text outputs must never be the only source of truth for later phases.

## 5) Integration restraint

Do not automatically register or wire a new agent into experiment YAML or pipeline topology unless explicitly requested.

Deliver the agent as a reusable component plus:
- registration path
- prompt path
- required config fields
- integration notes

## 6) Prompt templates

Prompt templates should:

- use explicit placeholders
- make missing domain-specific content obvious
- avoid hidden assumptions
- avoid mixing extraction, arbitration, and planning in one template unless explicitly required

## 7) Testing expectation

When agent behavior is mechanism-relevant, include tests for:

- successful structured output parsing
- invalid structured output handling
- boundary conditions
- validator interaction if applicable

## 8) Current Phase 1 bias

During Phase 1, agent code should primarily support:

- case structuring
- evidence atomization
- schema-compliant extraction

Do not prematurely turn Phase 1 agents into full diagnostic or arbitration agents.