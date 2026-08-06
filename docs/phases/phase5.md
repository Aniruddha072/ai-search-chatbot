# Phase 5 — Query Planning

**Commit:** `c9d39bb` (feat(planning): implement QueryPlanner and GroqClient)

## What we built
- `src/config/prompts/query_planner.txt` + `query_planning.py`: the system prompt as plain text (not a Python string literal, per explicit request) plus the `QueryPlanResponse` Pydantic schema (`intent`, `complexity: Literal["simple","moderate","complex"]`, `queries: list[str]` bounded 1-5).
- `src/infrastructure/llm/groq_client.py`: `GroqClient`, the first concrete `LLMProvider` - implements both `generate()` (capable model, plain text) and `generate_structured()` (fast model, `response_format={"type": "json_object"}` + Pydantic validation).
- `src/application/query_planner.py`: `QueryPlanner.plan(user_query) -> Query`, wrapping the Groq call in `asyncio.wait_for`, mapping a valid response into a domain `Query`, and falling back to a single-query `Query` built from the raw question on any failure (timeout, network error, schema validation failure).
- Three new `Settings` fields, documented in `.env.example`: `groq_fast_model`, `groq_capable_model`, `llm_timeout_seconds`.
- New dependency: `groq` (the actually-installed version, 1.6.0, checked rather than guessed).
- Six test files/additions: `test_groq_client.py`, `test_query_planner.py` (fallback on exception, malformed JSON, over-5-queries, and timeout), and a gated `tests/integration/test_query_planner.py` making one real Groq call.

## What we learned
- Verified against the live Groq API before designing anything: `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` (the two models the architecture doc already named) are both live, but **neither supports strict `response_format: json_schema`** - only `openai/gpt-oss-20b`/`120b` do, discovered by a real 400 error, not documentation.
- A second real test then showed *why* the "just switch models" instinct was premature: `json_object` mode + a **raw `model_json_schema()` dump** in the prompt caused `llama-3.1-8b-instant` to echo schema metadata (`{"title": "...", "type": "string"}`) as if it were the answer, on 2 of 3 test questions. Replacing that with a hand-written natural-language description + one worked example fixed it to 3/3. The lesson: a JSON Schema is for validators, not necessarily good in-context guidance for a small model - these are different audiences even though they describe the same shape.
- Checked the actually-installed `groq` package version (1.6.0) before writing a version constraint, rather than guessing a plausible-looking number.

## Key design decisions
- Kept Decision 1.5's original model choice (`llama-3.1-8b-instant` for planning) rather than switching to `openai/gpt-oss-20b` for API-enforced schema compliance - the roadmap already mandates a fallback path for malformed output, so the small residual risk of `json_object` mode isn't actually uncovered risk.
- `GroqClient` implements `generate()` fully now even though nothing calls it until Phase 6 - `abc.ABC` requires every abstract method overridden before instantiation is even possible, so there's no such thing as a partial `LLMProvider` implementation.
- `llm_timeout_seconds` is named generically, not "query-planning-specific" - Phase 6's `AnswerGenerator` will need the identical kind of Groq-call timeout, so one Settings field covers both rather than adding a near-duplicate later.
- Two independent enforcement points for the same 1-5 invariant: `QueryPlanResponse.queries` rejects a >5-item list at the schema layer before `Query.__post_init__` (Phase 1) would ever see it - neither layer trusts the other to have already checked.
- The prompt lives in a `.txt` file, not a Python string constant, so prompt wording can be edited without touching code.

## Challenges faced
- The Groq structured-output model mismatch above required stopping mid-design and testing two full alternative strategies empirically before choosing - documented as Decision 5.1 below rather than silently picked.
