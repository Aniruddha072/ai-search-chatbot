# Phase 6 — Answer Generation

**Commit:** `162b3d0` (feat(generation): implement AnswerGenerator with cite-or-refuse grounding)

## What we built
- `src/config/prompts/answer_generation.txt` + `answer_generation.py`: the cite-or-refuse system prompt (plain text, no schema - this is free-text generation, not structured output), loaded the same way `query_planner.txt` was in Phase 5.
- `src/application/answer_generator.py`: `AnswerGenerator.generate(query, sources) -> Answer` - formats an indexed source block, calls `LLMProvider.generate()` (Groq's capable model) wrapped in `asyncio.wait_for(llm_timeout_seconds)`, then extracts `[n]` citation markers via regex, maps them back to the actual `Source` objects (deduped, sorted, invalid indexes silently dropped), and returns an `Answer`.
- No changes to `domain/interfaces.py`, `groq_client.py`, or `Settings` - everything this phase needed already existed from Phase 5 (`GroqClient.generate()` was implemented in full then specifically because it was known this phase would need it - see Decision 5.2).
- Four test files/additions: `test_answer_generator.py` (prompt formatting, citation mapping, dedup, out-of-range citation handling, no-citation case, exception propagation, timeout propagation) and a gated `tests/integration/test_answer_generator.py` making one real Groq call.

## What we learned
- Verified live before writing the prompt (same discipline as Phase 5): `llama-3.3-70b-versatile` correctly used separate `[1][2]` brackets rather than combined `[1,2]`, correctly avoided citing an irrelevant source when asked a question it didn't answer, and correctly refused rather than hallucinating when given only irrelevant sources.
- The first version of that refusal test had a real quirk: the model cited `[1]` even while explicitly calling that source irrelevant. Adding one line to the prompt ("Only cite a source next to a claim it actually supports... cite nothing" on refusal) fixed it - verified by re-running both the refusal case (fixed) and the original positive-citation case (still correct) before locking in the wording.

## Key design decisions
- `AnswerGenerator` does not catch LLM failures the way `QueryPlanner` does - there's no safe fallback answer possible without a successful LLM call, unlike planning's "just search the raw question." Failures propagate; deciding the user-facing behavior is explicitly a Phase 7/10 concern per the existing degradation ladder in decisions.md.
- Streaming is deferred to Phase 11, despite the roadmap checklist's literal "streaming-capable" wording. `AnswerGenerator` needs the complete response regardless (citation parsing can't work on a partial stream), and building streaming now would mean designing it with no real consumer to validate against until the CLI exists.
- Citation parsing is defensive: duplicate citations of the same source are deduplicated, and a hallucinated out-of-range index (e.g. `[99]` when only 2 sources exist) is silently dropped rather than raising - matches the project's general pattern of not trusting a single validation point.

## Challenges faced
- None blocking. The refusal-citation quirk was caught and fixed during design (before any code was written), the same way Phase 5's prompt issues were - verify against the real API first, write code second.
