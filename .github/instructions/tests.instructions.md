---
applyTo: "tests/**/*.py"
---

# Test Instructions

When adding or editing tests in this repository:

## 1) Prefer mechanism-level tests

Prefer tests that validate:

- schema behavior
- validator behavior
- provenance checks
- stage consistency
- event logging
- write gating
- backward compatibility

Do not over-rely on prompt snapshot tests.

## 2) Include failure cases

Every important mechanism should have tests for:

- success path
- invalid input
- boundary condition
- expected blocked write
- expected validation report

Do not only test the happy path.

## 3) Fixture style

Fixtures should be:

- small
- readable
- stage-aware
- clinically plausible in ILD MDT text reasoning

Prefer fixtures that resemble:

- initial review
- supplementary test arrival
- follow-up revision trigger

## 4) Assertions

Prefer asserting:

- structured fields
- ids
- provenance references
- validator outputs
- stage alignment
- explicit failure categories

Avoid vague assertions like “output looks reasonable”.

## 5) Current Phase 1 focus

During Phase 1, prioritize tests for:

- `EvidenceAtom`
- `ClaimReference`
- `HypothesisState`
- `StateValidationReport`
- unsupported claim blocking
- stage-aware state construction
- event log replay compatibility