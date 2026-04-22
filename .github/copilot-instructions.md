# AgentLabILD / ILD-MDT Research Platform — Repository Instructions

## 1) Project identity

This repository is a **research platform**, not a product demo.

Its purpose is to study **mechanism-governed medical multi-agent reasoning** in the ILD MDT setting.

The project does **not** center on “making agents look more like doctors”.
The current research center is:

- explicit hypothesis state management
- controlled information sharing
- typed conflict explicitation and escalation
- local belief revision under new evidence
- arbitration and safety gate

When there is tension between “adding another agent” and “strengthening a system mechanism”, prefer the mechanism.

---

## 2) Domain scope

This project focuses on **text-based clinical reasoning** for ILD MDT.

Important scope constraints:

- no medical image processing
- no pathology slide processing
- radiology and pathology inputs are text reports only
- the goal is clinically reviewable reasoning state, not polished prose

All implementations should support staged clinical reasoning such as:

- initial review
- supplementary examination
- follow-up review
- revised working diagnosis

---

## 3) Core research principle

Mechanism first, agent second.

Prefer implementing:

- explicit state objects
- validators
- write gates
- typed protocols
- audit logs
- deterministic constraints
- versioned state transitions

over implementing:

- extra role prompts
- longer prompt instructions
- free-text inter-agent discussion
- hidden control logic inside prompts
- “smart” agents that silently decide system behavior

Prompting may assist generation, but core control must be enforced by executable external mechanisms.

---

## 4) Current implementation priority

The current development priority is **Phase 1: explicit state externalization**.

Implementation order should usually be:

1. schema
2. provenance
3. validators
4. state writer
5. storage / versioning
6. adapter agents
7. orchestration integration

Do not jump directly to rich multi-agent dialogue, arbitration logic, or conflict resolution before the state layer is stable.

---

## 5) Hard invariants for Phase 1 and state-related code

For any code touching schema, state, validators, writer, storage, or extraction:

- no free-text diagnostic conclusion may be written directly into shared state
- every claim must reference evidence ids, not informal prose evidence
- every evidence object must include provenance
- every state object must be stage-aware
- every persistent state write must pass validation first
- unsupported claims must be blocked or explicitly reported
- state must support future versioned revision
- case structuring code must not output final diagnosis
- evidence extraction code must not silently merge into diagnosis reasoning
- if uncertainty exists, preserve uncertainty explicitly rather than forcing a single conclusion

If a requested change conflicts with these invariants, preserve the invariants.

---

## 6) Engineering principles

- backend only
- Python 3.11+
- configuration-first design
- prompt files are external resources, not embedded code
- reproducibility matters
- traceability matters
- keep modules small and composable
- prefer explicit names over clever abstractions
- prefer Pydantic models and explicit validation over loose dictionaries
- do not overengineer before a measured need appears
- keep backward compatibility when reasonable

---

## 7) Modification policy

Only implement the requested unit of work.

Do not silently:

- change pipeline topology
- register new components into experiment YAML unless explicitly asked
- modify unrelated agents
- replace old behavior without a compatibility path
- add front-end code
- convert mechanism work into prompt-only work

Prefer delivering isolated reusable parts with clear integration instructions.

---

## 8) Validation requirements

For every non-trivial change:

- add or update tests
- explain how to validate the change
- append a short entry to `docs/devlog.md`
- add a teaching note under `teach/`
- document expected runtime data flow when relevant

When implementing a mechanism, tests are mandatory.
When implementing only prompts or examples, explain why no mechanism-level test is possible.

---

## 9) Output style for generated code

- runtime prompts and role prompts may use English
- engineering docs, comments, and teaching notes should primarily use Chinese
- code should be readable and explicit
- avoid magical helper layers unless they reduce real complexity
- prefer deterministic post-processing when possible
- avoid giant files; split by responsibility

---

## 10) Phase 1 interpretation

Interpret Phase 1 as building the **explicit state layer** for staged ILD reasoning.

Preferred building blocks include:

- `StageContext`
- `EvidenceAtom`
- `ClaimReference`
- `HypothesisState`
- `ActionCandidate`
- `HypothesisBoardInit`
- `StateValidationReport`
- `StateEvent`

The main deliverable is **not** “an extraction agent”.
The main deliverable is a validated state representation that later phases can safely build on.

---

## 11) Research framing guidance

Treat the following as distinct:

- clinical concept
- system mechanism
- evaluation metric
- engineering convenience

Do not collapse them into one object.

Examples:

- “premature closure” is a clinical / cognitive failure concept
- “top-k differential preservation” is a system mechanism
- “differential retention rate” is an evaluation metric
- “cached LLM call” is an engineering convenience

When implementing, keep these layers conceptually separate.

---

## 12) What Copilot should optimize for

Optimize for:

- auditability
- traceability
- staged reasoning compatibility
- future belief revision
- safe integration into later phases

Do not optimize only for:

- short demos
- minimal token count
- elegant free-text output
- superficially complete single-pass diagnosis