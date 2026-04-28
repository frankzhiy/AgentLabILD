# Phase 1 Prompt Template Renderer (2026-04-28)

## Analysis path

1. Inspected `configs/prompts/v2/case_structurer.md` and `configs/prompts/v2/evidence_atomizer.md` because they are the current prompt contracts loaded by the adapter-like Case Structurer and Evidence Atomizer modules.
2. Inspected `src/agents/case_structurer.py` and `src/agents/evidence_atomizer.py` to confirm the current compatibility path: those modules still read prompt files as text and append input JSON themselves.
3. Inspected existing adapter and validator boundaries to keep this change limited to prompt composition only, without adding LLM calls or persistence behavior.

## Change list

1. `src/prompts/template_renderer.py`
   - Added a small renderer for `{{variable_name}}` placeholders.
   - Added missing-variable and malformed-placeholder errors.
   - Added stable JSON serialization for dict, list/tuple, and Pydantic model values.
2. `src/prompts/__init__.py`
   - Exported the renderer functions and error types.
3. `configs/prompts/v2/case_structurer.md`
   - Converted the static prompt contract into a renderable template with `{{output_schema_json}}` and `{{input_json}}`.
4. `configs/prompts/v2/evidence_atomizer.md`
   - Converted the static prompt contract into a renderable template with the same explicit placeholders.
5. `tests/test_prompt_template_renderer.py`
   - Added tests for placeholder replacement, missing variables, malformed placeholders, stable JSON serialization, Pydantic serialization, and both prompt files.

## Connection mechanism

The new renderer is discovered through `src.prompts`. Future LLM-backed agents should call `render_template_file()` with:

- `input_json`: the stage/source payload to present to the model
- `output_schema_json`: the target structured-output schema

The existing compatibility modules can still load the markdown prompt files as text, so this change does not require adapters or validators to change yet.

## Runtime data flow

1. Caller prepares a variable mapping such as `{"input_json": payload, "output_schema_json": schema}`.
2. `render_template_file()` reads the markdown template.
3. `render_template()` finds all `{{...}}` placeholders and verifies each variable exists.
4. `serialize_prompt_value()` converts dict/list/Pydantic values to deterministic JSON with sorted keys.
5. The rendered prompt string is returned to the caller.
6. No LLM provider is called, no adapter parser is invoked, and no authoritative state is written.

## Self-service modification guide

- To add a new prompt variable, add a `{{variable_name}}` placeholder to the markdown template and pass the same key in the renderer variable mapping.
- To adjust serialization behavior, edit `serialize_prompt_value()` in `src/prompts/template_renderer.py`.
- To add another prompt template, place the markdown under `configs/prompts/v2/` and add a render test using `render_template_file()`.
- Do not put provider calls, adapter parsing, validation, or state writes inside the renderer.

## Validation method

Run:

```bash
python -m pytest -q tests/test_prompt_template_renderer.py
python -m pytest -q
```

Expected output:

- The focused renderer tests pass.
- The full repository test suite passes.

Common failure causes:

- A template references a placeholder not supplied by the caller.
- A placeholder uses an invalid name such as `{{input-json}}`.
- A template has unmatched `{{` or `}}` delimiters.
- A test expects static prompt text but the prompt has been converted into a template.

## Concept notes

- Prompt composition is separate from LLM invocation. Rendering only produces text; it does not decide which model to call or how to parse model output.
- Stable JSON matters because prompt diffs, traces, and tests become reproducible when keys are sorted and formatting is deterministic.
- Explicit placeholders keep prompt inputs visible and reviewable instead of hiding payload assembly inside ad hoc string concatenation.
