# Phase 1 LLM Structured Runner and Schema Export (2026-04-28)

## Analysis path

1. Inspected `src/llm/__init__.py` because the LLM package was still a skeleton and was the intended home for provider-independent LLM contracts.
2. Inspected `src/agents/case_structurer.py` and `src/agents/evidence_atomizer.py` to confirm Issue 2 should not place provider calls in current adapter-like prompt/parser modules.
3. Inspected `src/adapters/case_structuring.py` and `src/adapters/evidence_atomization.py` to confirm schema export should work against existing Pydantic draft models without changing adapter contracts.
4. Inspected prompt renderer code to keep Issue 2 separate from prompt composition: the runner receives already-rendered prompts or messages.

## Change list

1. `src/llm/provider_config.py`
   - Added `LLMProvider` and `LLMProviderConfig` for provider/model settings.
   - Does not create SDK clients or read API keys.
2. `src/llm/schema_export.py`
   - Added deterministic Pydantic JSON schema export helpers.
   - Supports dict export and stable pretty JSON export.
3. `src/llm/retry_policy.py`
   - Added retry policy constrained to `transport`, `timeout`, and `malformed_json`.
   - Explicitly rejects configuration that would retry adapter/validator-style failures.
4. `src/llm/structured_runner.py`
   - Added injectable `StructuredLLMClient` protocol and `StructuredLLMRunner`.
   - Runner accepts rendered prompt strings or rendered chat messages.
   - Runner returns normalized success/failure/manual-review result objects.
5. `src/llm/__init__.py`
   - Exported the new contracts.
6. LLM tests
   - Added deterministic offline tests for schema export, retry policy, and structured runner behavior.

## Connection mechanism

Future real agents should compose prompts first, then call `StructuredLLMRunner` with:

- a rendered prompt or rendered messages
- optional output schema from `export_pydantic_json_schema()`
- an injected client implementing `StructuredLLMClient`

The runner returns a `StructuredLLMRunnerResult`. Adapter parsing, validator execution, and state writing remain separate downstream steps.

## Runtime data flow

1. A caller builds a rendered prompt or message tuple outside the runner.
2. A caller exports a target response schema from a Pydantic model when needed.
3. `StructuredLLMRunner` builds a `StructuredLLMRequest`.
4. The injected client receives the request and performs provider-specific work.
5. The runner normalizes the response content:
   - dict content is accepted as already structured.
   - JSON string content is parsed.
   - malformed JSON can be retried by policy.
6. The runner returns success, failure, or manual-review status.
7. No adapter rejection, validator rejection, authoritative state construction, or state write is repaired or bypassed in this layer.

## Self-service modification guide

- Add provider SDK integration by writing a client object that implements `complete(request)`.
- Keep API-key loading and SDK calls out of adapters and validators.
- Adjust retry count or retryable kinds through `StructuredLLMRetryPolicy`; only transport, timeout, and malformed JSON are allowed in Issue 2.
- Use `export_pydantic_json_schema_json()` when a stable schema string is needed for prompt traces or test snapshots.

## Validation method

Run:

```bash
python -m pytest -q tests/test_llm_schema_export.py tests/test_llm_retry_policy.py tests/test_llm_structured_runner.py
python -m pytest -q
```

Expected output:

- Focused LLM tests pass offline with fake clients.
- Full repository suite passes.

Common failure causes:

- A fake client returns a non-dict/non-string object.
- A response string contains JSON that is not an object.
- Retry policy is configured with a non-allowed failure kind.
- A caller tries to construct a request with both prompt and messages.

## Concept notes

- LLM invocation is isolated from adapters so adapters stay as boundary parsers for candidate model output.
- Structured runner output is still non-authoritative. It becomes meaningful only after adapter parsing and validator-gated state writes.
- Fake-client injection keeps tests deterministic and prevents accidental network or API-key dependency.
