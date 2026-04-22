# AGENTS.md

## Purpose

This repository may use agent-like components, but agents are **not** the main research contribution.

Agents should be treated as adapters into externally governed mechanisms.

If a request can be satisfied either by:
- expanding agent behavior, or
- strengthening schema, validator, protocol, gate, or state logic,

prefer the second unless the user explicitly requests otherwise.

---

## Working Style

### 1. Minimal delivery

Only build the requested unit of work.

If asked to add:
- an agent: add only the agent, its prompt template, registration hook, and tests if appropriate
- a schema: add only the schema, validators, and tests
- a protocol: add only the protocol objects and integration notes

Do not silently wire the new part into experiment configs, pipelines, or YAML unless explicitly requested.

---

### 2. Lego-style delivery

Produce reusable parts, not forced assembly.

Each addition should clearly state:
- what was added
- where it lives
- how it is discovered by the framework
- how the user can integrate it later
- what placeholders still require user or domain decisions

If a prompt template contains domain-sensitive instructions, use explicit placeholders and label them clearly.

---

### 3. Mechanism boundary

Do not let an agent silently take over responsibilities that belong to system mechanisms.

Examples:

- `Case Structurer` must not produce a final diagnosis
- `Evidence Atomizer` must not arbitrate between hypotheses
- `Conflict Agent` must not invent or delete evidence
- `Arbiter` must not bypass safety or validation gates

If such a boundary is at risk, preserve the mechanism boundary.

---

### 4. Teaching documentation is mandatory

After any non-trivial code change, create a markdown note under `teach/`.

The teaching note must include:

1. **Analysis path**  
   Which files were inspected first and why they were the right starting point

2. **Change list**  
   Which files were added or modified, what changed in each file, and why

3. **Connection mechanism**  
   How the new code is discovered and called by the existing framework

4. **Runtime data flow**  
   How data moves through the modified code at runtime, from input to output

5. **Self-service modification guide**  
   What the user should edit later if they want to adjust or extend the change

6. **Validation method**  
   Which commands to run, what output is expected, and what common failure causes to check first

7. **Concept notes**  
   Programming concepts, framework concepts, and design ideas involved in the change

This note is part of the deliverable, not an optional extra.

---

### 5. Devlog update is mandatory

For any non-trivial change, append a concise entry to `docs/devlog.md` including:
- date
- task name
- files changed
- why the change was needed
- how it was validated

---

### 6. Tests and failure cases

When a mechanism is added or changed, include tests for:
- success cases
- expected failure cases
- validation failures
- boundary conditions

Do not test only the happy path.

---

### 7. Integration restraint

Do not silently:
- edit experiment configs
- change pipeline graph structure
- swap default protocols
- replace old components
- introduce hidden coupling across unrelated modules

Explain how to integrate the new part instead.

---

### 8. Preferred explanation style

When generating docs or teaching notes:
- explain concretely
- prefer file names, call paths, and state flow
- avoid vague statements like “the framework will handle it”
- clearly distinguish between:
  - established facts
  - reasonable inferences
  - optional future extensions

---

### 9. Current project emphasis

At the current stage, the platform emphasis is:

1. explicit state
2. provenance
3. validator-gated writes
4. staged reasoning compatibility
5. future local revision

This means:
- schema work usually has higher priority than new agents
- state stability usually has higher priority than richer orchestration
- auditability usually has higher priority than conversational polish