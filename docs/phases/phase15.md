# Phase 15 — Conversation-aware query resolution

**Commit:** _(pending)_

## What we built
- `src/domain/entities.py`: two new plain, immutable entities - `ConversationTurn` (a question plus a truncated answer summary) and `ConversationContext` (a tuple of turns), the same shape/dependency rules `Query`/`Source` already follow.
- `src/application/query_planner.py`: `QueryPlanner.plan()` gains an optional `conversation: ConversationContext | None = None` parameter. When present, its content is composed into the prompt sent to Groq (`_compose_prompt()`) instead of a separate rewrite call, and a SHA-256 digest of the conversation is folded into the cache key (`_cache_key()`) so two different conversations asking the same literal follow-up can't collide on one cached plan. Both default to `None`/no-history behavior identical to before this phase.
- `src/config/prompts/query_planner.txt`: a short addition teaching the model to resolve references against an optional `Recent conversation:` block, plus one worked example.
- `src/application/pipeline.py`: `ChatPipeline.handle()`, `handle_streaming()`, and `_prepare()` all thread the same optional `conversation` parameter through, unchanged for any caller that doesn't pass one.
- `src/config/settings.py`: new `conversation_history_turns` setting (default 2, `0` disables the feature entirely).
- `src/presentation/conversation_context.py` (new): `build_conversation_context()`, a small pure function that pairs up `st.session_state.messages` into `ConversationTurn`s, keeps only the most recent `max_turns`, and truncates each stored answer to 300 characters. Split out of `streamlit_app.py` itself specifically so it's importable and unit-testable without executing that file's top-level Streamlit calls (`st.set_page_config()`, `st.chat_input()`, etc.) - the same reasoning Phase 12 used when it extracted `cli.py`'s testable helpers.
- `src/presentation/streamlit_app.py`: builds a `ConversationContext` from `session_state` before each turn (from messages as they stand *before* the current question is appended, so it only ever contains prior, completed turns) and passes it into `handle_streaming()`.
- 19 new unit tests across `test_entities.py`, `test_query_planner.py`, `test_pipeline.py`, `test_settings.py`, and a new `test_conversation_context.py` - all touched files sit at 100% statement coverage.

## What we learned
- Reference resolution didn't need a second LLM call. Folding it into `QueryPlanner`'s existing Groq call (rather than a dedicated "rewrite this question standalone" call, the more textbook RAG pattern) keeps this at zero additional Groq calls per turn, since it's genuinely the same category of work the planner already does - deciding what the user wants before turning it into search queries.
- The pre-existing query-plan cache had a real, previously-latent correctness bug this phase surfaced: its key was the normalized question text alone, so two different conversations both asking "which one is cheapest?" would have collided and one could have silently been served the other's cached plan. Not something that could happen before this phase (there was no such thing as two different "which one is cheapest?" conversations), but a real bug the moment conversation-dependent planning existed - fixed by folding a digest of the conversation into the key.
- Live verification (real Tavily + Groq, not mocked) was necessary and caught something a mocked test never could: whether the real model actually uses the `Recent conversation:` block correctly. It did, on every turn of a real 5-question conversation - see the walkthrough below.
- The sliding window's behavior on a genuine topic-continuation question (turn 4, "What about VIT?") was more interesting than the original hypothetical walkthrough in the design proposal predicted: rather than a narrow restatement, the real model treated it as a comparison against whatever was actually in the window (COEP's cost and placements), which is exactly what a bounded window is supposed to produce - the effective topic shifts forward as older turns age out, without any explicit topic-tracking logic.

## Key design decisions
See `docs/decisions.md`, Decisions 15.1-15.3, for the full reasoning behind folding resolution into the existing Groq call, the sliding-window/cache-key-fix design, and the live-verification results.

## Live verification: the real 5-question conversation

Run against `build_demo_pipeline()` (real Tavily + Groq, `NullEvaluator`), one process, `conversation_history_turns` at its default of 2.

| Turn | Question | Window used | Resolved sub-queries |
|---|---|---|---|
| 1 | best engineering colleges in Pune? | *(none)* | `best engineering colleges in Pune`, `top engineering colleges in Pune` |
| 2 | which one is cheapest? | Turn 1 | `Symbiosis Institute of Technology fees`, `College of Engineering Pune fees`, `Vishwakarma Institute of Technology fees`, `MIT World Peace University fees`, `PCCOE Pune fees` |
| 3 | what about its placement record? | Turns 1-2 | `placement record COEP`, `COEP Pune alumni placement statistics` |
| 4 | What about VIT? | Turns 2-3 | `COEP Pune placement record`, `VIT Pune placement record`, `COEP Pune vs VIT Pune fees`, `VIT Pune vs COEP Pune ranking`, `VIT Pune vs COEP Pune infrastructure` |
| 5 | And last year's cutoff? | Turns 3-4 | `COEP Pune cutoff 2026`, `VIT Pune cutoff 2026`, `placement record of COEP Pune 2026`, `placement record of VIT Pune 2026` |

Turn 2 correctly expanded "which one" against every college named in turn 1's answer. Turn 3 correctly resolved "its" to COEP specifically - the one turn 2's answer had identified as cheapest, not just "a college." Turn 4 shows the window having already dropped turn 1: rather than a bare "VIT placements" lookup, the model produced a genuine COEP-vs-VIT comparison across both topics still present in the window (cost and placements) - a reasonable reading of an inherently underspecified question. Turn 5 correctly carried both colleges still in scope forward into the cutoff query.

## Challenges faced
No structural surprises - the design proposed in the GitHub issue (#3) before any code was written matched what actually got built, including the cache-key fix and the decision to split `conversation_context.py` out of `streamlit_app.py` for testability. The one real finding was empirical rather than architectural: confirming, via the live run above, that the real model's interpretation of an ambiguous topic-continuation question (turn 4) was sensible rather than just technically-plausible - something no mocked unit test could have shown either way.
