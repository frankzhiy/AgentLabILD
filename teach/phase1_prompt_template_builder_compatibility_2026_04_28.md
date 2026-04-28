# Phase 1 Prompt Template Builder Compatibility (2026-04-28)

## Analysis path

1. Inspected `src/agents/case_structurer.py` and `src/agents/evidence_atomizer.py` because their `build_*_prompt()` functions still loaded prompt files as static text.
2. Inspected `configs/prompts/v2/case_structurer.md` and `configs/prompts/v2/evidence_atomizer.md` because they now contain `{{input_json}}` and `{{output_schema_json}}` placeholders.
3. Inspected prompt-renderer tests to reuse the new `render_template_file()` contract instead of adding another rendering path.

## Change list

1. `src/agents/case_structurer.py`
   - Updated `build_case_structurer_prompt()` to render the template through `render_template_file()`.
   - Passes the existing input payload object as `input_json`.
   - Passes `CaseStructuringDraft.model_json_schema()` as `output_schema_json`.
   - Keeps the old static-contract-plus-input fallback when the prompt file is missing or empty.
2. `src/agents/evidence_atomizer.py`
   - Updated `build_evidence_atomizer_prompt()` with the same renderer path.
   - Passes `EvidenceAtomizationDraft.model_json_schema()` as `output_schema_json`.
3. `configs/prompts/v2/*.md`
   - Kept headings compatible with old tests by using `### Input JSON` and `### Output Schema JSON`.
4. Adapter prompt tests
   - Added checks that prompts contain no unresolved placeholders, include schema and input JSON, and include only one input section.

## Connection mechanism

The old public functions still live at:

- `src.agents.case_structurer.build_case_structurer_prompt`
- `src.agents.evidence_atomizer.build_evidence_atomizer_prompt`

They now call `src.prompts.render_template_file()` when the configured prompt file exists and is non-empty. This preserves current imports while making the prompt files truly renderable.

## Runtime data flow

1. The legacy builder constructs the same stage/source payload as before.
2. The builder passes that payload and the target Pydantic JSON schema to `render_template_file()`.
3. The renderer serializes both objects into stable JSON and substitutes template placeholders.
4. The prompt string is returned.
5. No LLM call, adapter migration, validation, state write, storage write, board schema change, or pipeline orchestration occurs.

## Self-service modification guide

- Edit prompt text in `configs/prompts/v2/*.md`.
- Keep `{{input_json}}` and `{{output_schema_json}}` placeholders unless the corresponding builder is updated.
- If the prompt file is intentionally removed or left empty, the builder falls back to the old static prompt behavior.
- Do not place provider calls or parsing logic in prompt builders.

## Validation method

Run:

```bash
python -m pytest -q tests/test_case_structurer_adapter.py tests/test_evidence_atomizer_adapter.py tests/test_prompt_template_renderer.py
python -m pytest -q
```

Expected output:

- Focused prompt/adapter tests pass.
- Full repository suite passes.

Common failure causes:

- Template placeholders are renamed without updating builder variables.
- Prompt files keep extra `{{...}}` placeholders that the renderer cannot resolve.
- A prompt test counts multiple `### Input JSON` sections, indicating duplicated old/manual input append behavior.

## Concept notes

- This compatibility fix bridges static prompt loading and renderable templates.
- The builder is still not a true LLM agent; it only composes prompt text.
- Schema JSON in prompts prepares for structured-output agents while keeping adapter parsing and validation as separate mechanisms.
