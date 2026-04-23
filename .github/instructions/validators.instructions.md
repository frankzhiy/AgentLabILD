---
applyTo: "src/validators/**/*.py"
---

# Validator Instructions

When editing validator code in this repository:

## 1) Mechanism-first boundary

Validators are external control mechanisms, not prompt-level helpers.
Validation behavior must be deterministic, auditable, and explicit.

## 2) Structured failure only

When validation fails, return structured issues.
Do not silently coerce, drop, or rewrite invalid authoritative content.

## 3) Non-mutation rule

Validators must treat authoritative state as read-only.
Do not mutate authoritative objects in place.
If a correction is needed, emit a separate proposed fix, not a mutated state.

## 4) Distinguishable failure taxonomy

At minimum, keep these failure classes distinguishable:

- schema failures
- provenance failures
- temporal failures
- unsupported-claim failures

Do not collapse these into one generic error bucket.
Use stable `issue_code` namespaces such as:

- `schema.*`
- `provenance.*`
- `temporal.*`
- `unsupported_claim.*`

## 5) ValidationIssue compatibility

Each validator issue should map cleanly to `ValidationIssue` fields:

- `issue_id`, `issue_code`, `severity`, `message`
- `target_kind`, `target_id`, `field_path` (when known)
- `related_ids`
- `blocking`
- `suggested_fix`, `non_authoritative_note` (optional)

## 6) StateValidationReport compatibility

Validator outputs should be directly represented as, or trivially convertible to,
`StateValidationReport` with:

- `report_id`, `case_id`, `stage_id`, `generated_at`
- `is_valid`, `has_blocking_issue`
- `issues`
- `validator_name`, `validator_version`, `summary`

Maintain internal consistency:

- `has_blocking_issue == any(issue.blocking for issue in issues)`
- write-gate decisions must not treat blocking reports as valid

## 7) Write-gate contract

Validators report; write layers enforce.
Blocking issues must prevent persistent writes.
Non-blocking issues must still be preserved in the report for auditability.

## 8) Current Phase 1 focus

Prioritize validator checks that protect:

- stage-aware consistency
- provenance traceability
- unsupported-claim blocking
- future local revision compatibility

Keep validator modules small, explicit, and composable.