---
applyTo: "src/schemas/**/*.py,src/state/**/*.py,src/storage/**/*.py,src/validators/**/*.py"
---

# Schema / State / Validator Instructions

When editing schema, state, storage, or validator code in this repository:

## 1) Primary rule

Mechanism first.

These files define system behavior boundaries.
Do not weaken them to accommodate convenient prompt outputs.

## 2) Modeling guidance

Prefer:

- explicit Pydantic models
- stable ids
- stage-aware objects
- discriminated unions when multiple record types coexist
- immutable or append-only event representations where appropriate
- explicit enums or literals for controlled fields

Avoid:

- raw nested dicts without validation
- untyped lists of mixed objects
- opaque free-text state blobs
- silently inferred structure that cannot be audited later

## 3) Required properties for key state objects

State-related objects should usually include some subset of:

- `id`
- `kind` or discriminant
- `stage_id`
- `created_at`
- `source_doc_id`
- `source_span`
- `version`
- `status`
- `evidence_ids`
- `confidence`
- `notes` only when notes are explicitly non-authoritative

Do not assume all objects need all fields.
Choose fields by responsibility, but preserve auditability.

## 4) Provenance rule

Every claim-like object must be traceable.

If an object asserts a diagnosis, interpretation, exclusion, or action rationale, it must be possible to trace it back to:

- evidence ids
- source spans
- originating stage

Free-text explanation is not a substitute for traceability.

## 5) Validation rule

All persistent writes must be validator-gated.

Typical validation layers may include:

- schema validity
- provenance validity
- temporal validity
- unsupported-claim detection
- duplicate / id collision checks
- stage consistency checks

If validation fails, return structured failure information.
Do not silently coerce invalid content into persisted state.

## 6) Temporal rule

Design state with future staged revision in mind.

Even if full belief revision is not implemented yet, schema decisions should not block later support for:

- initial review
- supplementary evidence
- follow-up update
- local claim revision
- snapshot comparison
- event replay

## 7) Backward compatibility

If legacy shallow state already exists, prefer:

- adapter layers
- compatibility fields
- migration helpers

Avoid breaking unrelated code unless explicitly requested.

## 8) Testing expectation

Any non-trivial schema/state/validator change should add tests for:

- valid construction
- invalid construction
- provenance failure
- temporal mismatch
- unsupported claims
- serialization / deserialization

## 9) Current Phase 1 bias

During Phase 1, prefer implementing:

- state ontology
- evidence representation
- claim reference
- validation reports
- state events
- storage contracts

over implementing:

- arbitration logic
- multi-agent debates
- free-text consensus generation