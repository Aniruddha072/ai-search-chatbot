# Design Decisions & Tradeoffs

Related docs: [Architecture](architecture.md) · [Roadmap & checklist](roadmap.md) · [Phase build logs](phases/)

---

## 0. Implemented Decisions (by phase)

Everything below section 1 is a **design decision made before writing the
corresponding code** - still accurate as *intent* for phases 3–14, which
aren't built yet. This section is different: it's decisions actually made
*during* implementation for phases that are done, including places where
reality corrected the plan. New entries get added here as each phase
completes; nothing here is retroactively rewritten.

### Decision 0.1

Date: 2026-08-06

Implemented:
`Settings` fields use `Field(..., min_length=1)`, not just `Field(...)`.

Reason:
- `pydantic-settings` treats an empty environment variable as a present,
  valid string - not a missing one.
- Without `min_length=1`, `GROQ_API_KEY=` (empty) would pass validation
  and fail confusingly later, deep inside whichever component first tried
  to use it.

### Decision 0.2

Date: 2026-08-06

Implemented:
Per-turn correlation ID uses `contextvars.ContextVar`, not a module-level
global variable.

Reason:
- The pipeline runs concurrent I/O (search fan-out via `asyncio.gather`
  starting Phase 2, more later) inside a single process.
- A plain global would let concurrent tasks overwrite each other's turn ID;
  a `ContextVar` keeps each concurrent call's value isolated.

### Decision 1.1

Date: 2026-08-06

Implemented:
`Query.sub_queries` is typed `tuple[str, ...]`, not `list[str]`.

Reason:
- `frozen=True` only blocks reassigning a field, not mutating an object it
  points to - a `list` field could still be `.append()`-ed to, silently
  bypassing the 1-5 invariant after construction.
- The dataclass's generated `__hash__` (from `frozen=True`) requires every
  field to be hashable; `list` isn't, `tuple` is.

### Decision 1.2

Date: 2026-08-06

Implemented:
The 1-5 sub-query bound is enforced in `Query.__post_init__`, raising
`ValueError` outside that range - not left to planner-prompt wording alone.

Reason:
- An out-of-range `Query` becomes impossible to construct regardless of
  which future code path builds one, including bugs in the Phase 5
  planner we haven't written yet.

### Decision 1.3

Date: 2026-08-06

Implemented:
Domain ports (`SearchProvider`, `LLMProvider`, `Ranker`, `Evaluator`,
`Cache`) are `abc.ABC` with `@abstractmethod`, not `typing.Protocol`.

Reason:
- ABCs are nominal and enforced at runtime: instantiating an incomplete
  implementation raises `TypeError` immediately.
- `Protocol` is structural and only checked by static type-checkers -
  explicit `class Foo(SearchProvider):` inheritance also makes the
  dependency visible directly in the code.

### Decision 1.4

Date: 2026-08-06

Implemented:
`LLMProvider.generate_structured`'s schema parameter is an unbound
`TypeVar`, not one bound to `pydantic.BaseModel`.

Reason:
- Keeps `domain/` free of any external dependency, even though the
  concrete Groq client (later phase) will pass Pydantic schemas at
  call sites.

### Decision 2.1

Date: 2026-08-06

Implemented:
`SearchOrchestrator.search_all()` accepts a `Query` entity instead of
`list[str]`.

Reason:
- Already validated (reuses the 1-5 invariant from Decision 1.2)
- Documents exactly where this class sits in the pipeline (right after
  planning)
- Self-describing signature over a "stringly-typed" list

### Decision 2.2

Date: 2026-08-06

Implemented:
`SearchOrchestrator` enforces its own per-query timeout via
`asyncio.wait_for`, rather than trusting each `SearchProvider`
implementation to enforce one internally.

Reason:
- Guarantees a bound regardless of what a given provider's SDK does -
  even if a future provider forgets to configure a timeout, the
  orchestrator's still applies.
- `asyncio.gather(..., return_exceptions=True)` then handles a timeout
  exactly like any other failure, with no extra branching.

### Decision 2.3

Date: 2026-08-06

Implemented:
No custom exception types (`SearchProviderError`, etc.) introduced yet -
whatever exception `tavily-python` raises natively propagates as-is.

Reason:
- Typed exceptions per layer are explicitly scoped to Phase 10 in the
  roadmap. Adding them now would be speculative infrastructure ahead of
  the need, for a class of problem (retries, error translation) that
  doesn't exist until Phase 10's resilience work.

### Decision 2.4

Date: 2026-08-06

Implemented:
The gated Tavily integration test reads `TAVILY_API_KEY` directly via
`python-dotenv`, instead of going through `get_settings()`.

Reason:
- Found *during* Phase 2: `get_settings()` validates the entire app
  config, including `GROQ_API_KEY` - which was still empty (not needed
  until Phase 5/6) and made a Tavily-only test fail for an unrelated
  reason.
- A test should only depend on what it actually exercises.

### Decision 3.1

Date: 2026-08-06

Implemented:
`Deduplicator` has no ABC/interface, unlike `SearchProvider`, `LLMProvider`,
`Ranker`, `Evaluator`, and `Cache`.

Reason:
- There's no second deduplication strategy this project plans to swap in
  later - an interface with only one implementation ever planned is an
  abstraction paying for flexibility nobody asked for.

### Decision 3.2

Date: 2026-08-06

Implemented:
Dedup similarity threshold and the three `HeuristicRanker` weights are
constructor-default constants, not `Settings` fields.

Reason:
- They're internal scoring heuristics, not ops-level configuration.
- No evidence yet exists about which values are actually better - that's
  literally what Phase 8's RAGAS scores are for.

### Decision 3.3

Date: 2026-08-06

Implemented:
Keyword overlap in `HeuristicRanker` uses plain token-set overlap, not
TF-IDF.

Reason:
- TF-IDF needs a document corpus to compute meaningful
  inverse-document-frequency; ~10-20 results per query isn't one.

### Decision 3.4

Date: 2026-08-06

Implemented:
`Ranker.rank()` scores each result against the *original* user query, not
the sub-query that produced it.

Reason:
- Matches the `Ranker.rank(results, original_query)` signature already
  fixed in Phase 1 - relevance should be judged against what the user
  actually asked, not the decomposed search string that happened to
  retrieve a given result.

### Decision 4.1

Date: 2026-08-06

Implemented:
Token counting uses a `len(text) // 4` character heuristic, not tiktoken.

Reason:
- Measured, not assumed: `tiktoken.get_encoding("cl100k_base")` took 15.5
  seconds on first call (it silently downloads its vocabulary file over
  the network), ~0.26s cached after. A hidden network dependency and
  15-second cold start is a real cost for a project explicitly about
  minimizing latency.
- Groq serves Llama models, which don't have a public tiktoken encoding
  anyway - cl100k_base would only be an approximation here too, so
  tiktoken isn't actually more correct, just heavier.

### Decision 4.2

Date: 2026-08-06

Implemented:
`ContentExtractor` is a domain interface (`abc.ABC`); `Deduplicator`
(Phase 3) is not.

Reason:
- The architecture doc explicitly names a real future swap (trafilatura
  vs. readability) for content extraction - it names no such alternative
  for deduplication. Same test as Decision 3.1, opposite outcome.

### Decision 4.3

Date: 2026-08-06

Implemented:
`ContextBuilder.build()` takes only `list[SearchResult]`, not a `Query`.

Reason:
- Decision 1.3's "or the query is comparison-heavy" full-fetch trigger
  needs `Query.complexity` semantics that don't exist until Phase 5's
  planner defines them. Only the snippet-length trigger is implemented
  now; the complexity-based one is deferred, not abandoned.

### Decision 4.4

Date: 2026-08-06

Implemented:
The per-fetch timeout lives in `ContextBuilder`, not
`TrafilaturaContentExtractor`.

Reason:
- Same separation Decision 2.2 established for `SearchOrchestrator`/
  `TavilyProvider` - reused rather than re-derived, so every
  infrastructure adapter stays timeout-agnostic and every
  orchestration-layer class enforces its own bound.

### Decision 4.5

Date: 2026-08-06

Implemented:
`context_token_budget`, `max_context_sources`, and
`content_fetch_timeout_seconds` are `Settings` fields, not constructor
defaults.

Reason:
- Unlike Phase 3's ranking weights (internal scoring heuristics), these
  directly control cost/latency/how-much-reaches-the-LLM - the same
  category Phase 2's `search_timeout_seconds`/`max_search_results` are
  already in.

### Decision 5.1

Date: 2026-08-06

Implemented:
Query planning uses `llama-3.1-8b-instant` with `response_format:
json_object` + Pydantic validation, not `openai/gpt-oss-20b` with strict
`json_schema` mode.

Reason:
- Verified live: neither `llama-3.1-8b-instant` nor `llama-3.3-70b-versatile`
  (the models Decision 1.5 already named) support Groq's strict
  `json_schema` response format - only the `openai/gpt-oss-*` models do.
- Tested the alternative before ruling it out: a raw `model_json_schema()`
  dump in the prompt caused `llama-3.1-8b-instant` to echo schema
  metadata as if it were the answer (2/3 test questions failed). A
  hand-written natural-language prompt + one example fixed it to 3/3.
- The roadmap already mandates a fallback path for malformed planner
  output, so `json_object` mode's smaller residual non-conformance risk
  isn't actually uncovered - keeping Decision 1.5's original model choice
  won out over chasing API-enforced strictness.

### Decision 5.2

Date: 2026-08-06

Implemented:
`GroqClient.generate()` (capable model, plain text) is fully implemented
in Phase 5, even though nothing calls it until Phase 6.

Reason:
- `abc.ABC` requires every `@abstractmethod` overridden before a class
  can be instantiated at all - there's no such thing as a partially
  implemented `LLMProvider`. This isn't building ahead into Phase 6, it's
  satisfying a contract Phase 1 already wrote in full.

### Decision 5.3

Date: 2026-08-06

Implemented:
The new Groq-call timeout setting is named `llm_timeout_seconds`, not
something query-planning-specific.

Reason:
- Phase 6's `AnswerGenerator` will need the identical kind of timeout
  around its own Groq call - one generically-named field covers both
  instead of adding a near-duplicate later.

### Decision 5.4

Date: 2026-08-06

Implemented:
The 1-5 sub-query bound is enforced twice: `QueryPlanResponse.queries`
(Pydantic `max_length=5`) and `Query.__post_init__` (Decision 1.2).

Reason:
- Neither layer trusts the other to have already checked. A >5-query
  Groq response is rejected at the schema layer before a domain `Query`
  is ever constructed from it.

### Decision 5.5

Date: 2026-08-06

Implemented:
The query-planning system prompt lives in `query_planner.txt`, not a
Python string constant.

Reason:
- Prompt wording can be edited without touching code - explicitly
  requested, and a pattern worth continuing for future prompts (Phase 6's
  answer-generation prompt).

---

## 1. Key design decisions

**1.1 One combined Groq call for intent + query generation, not two.**
Classifying intent and generating queries are related enough that a single
structured-output call (JSON mode with a schema: `{intent, complexity,
queries: [...]}`) does both for the token/latency cost of one call. Splitting
them into "classify, then plan" would double planning latency for no accuracy
gain at this scope.

**1.2 Query count is LLM-decided, not rule-based.**
A regex/keyword heuristic for "complexity" (e.g., counting clauses) is
brittle and doesn't generalize. Instead the planner prompt gives the model
explicit criteria (single fact → 1 query; comparison/ranking/multi-attribute
→ 3–5) and the model returns the count directly, capped at 5 by the response
schema (`maxItems: 5`) as a hard backstop.

**1.3 Snippet-first context, selective full-fetch — not one or the other.**
Tavily snippets are usually enough for factual grounding and cost near-zero
extra latency. But for the top 2–3 ranked sources, if the snippet is short
(< ~40 words) or the query is comparison-heavy, the ContextBuilder fetches
and extracts the actual page. This directly answers constraint #9 ("choose
whichever improves accuracy") without paying full-page-fetch latency on every
source.

**1.4 Heuristic ranking now, embedding rerank later — behind one interface.**
An embedding/cross-encoder reranker would improve relevance ordering but adds
a model dependency, latency, and (if using a hosted embedding API) cost and
another external failure point. For an internship-scope MVP, a transparent
heuristic (keyword/TF-IDF overlap with the *original* query + recency +
provider score) is explainable, has zero extra latency, and is correct
often enough. Because `Ranker` is a port, upgrading to embeddings later is a
one-file change — call this out explicitly in the internship writeup as a
deliberate MVP-vs-ideal tradeoff, not an oversight.

**1.5 Model tiering on Groq.**
Query planning uses a small/fast Groq model (e.g. `llama-3.1-8b-instant`);
final answer generation uses a larger model (e.g. `llama-3.3-70b-versatile`).
Planning is a short structured-output task where the small model is reliable;
answer quality is what the user actually judges, so it gets the bigger model.
This alone is one of the larger latency/cost wins available (the planning
call is 3-5x cheaper and faster than the generation call).

**1.6 RAGAS runs reference-free, synchronously, but non-blocking on failure.**
Because there's no ground-truth answer at chat time, only reference-free
RAGAS metrics apply: **faithfulness** (is the answer supported by the
retrieved context — the most important one for a grounded chatbot),
**answer relevancy** (does the answer address the question), and **context
precision** (is the retrieved context actually useful). `context_recall`
needs a reference answer and is deliberately left for an *offline* eval
harness (a curated test set), not the live path. RAGAS calls run after
generation (they need the answer) but its 2–3 metric computations run
concurrently via `asyncio.gather`. If RAGAS itself errors or times out, the
pipeline still returns the answer with `evaluation: null` rather than failing
the user-facing turn — evaluation is an observability feature, not a gate the
user should ever be blocked on.

**1.7 CLI first.**
Validates the pipeline end-to-end fastest. `ChatPipeline` is presentation-
agnostic by construction, so `api.py` is additive later, not a rewrite.

---

## 2. Tradeoffs summary

| Decision | Gains | Costs | Mitigation |
|---|---|---|---|
| Single search provider | Simpler, meets constraint, cheaper | Coverage limited to one index | Interface allows swap/fan-out later |
| Snippet-first, selective fetch | Fast, cheap | Occasionally thinner context than full pages | Full-fetch triggers for top-K + short snippets |
| Heuristic ranking (no embeddings) | No extra model/latency/cost | Lower ranking precision than semantic rerank | Ranker port makes upgrade a one-file change |
| Sync RAGAS in the request path | User sees eval score immediately (per spec) | Adds real latency (RAGAS = more LLM calls) | Parallelize metrics; fail-open (don't block answer) |
| LLM-decided query count | Generalizes better than rules | Occasional over/under-generation | Hard cap at 5 in schema; min 1 enforced by validation |
| In-memory cache by default | Zero infra to start | Doesn't survive restarts, not multi-instance | `Cache` port swaps to Redis with one config change |

---

## 3. Performance optimizations

- **Parallel search fan-out** — all sub-queries hit Tavily concurrently via `asyncio.gather`, not sequentially.
- **Model tiering** — small/fast model for planning, larger model only for the user-facing answer.
- **Streaming the final answer** — Groq supports token streaming; the CLI (and later API via SSE) should stream the answer as it's generated rather than waiting for the full completion, so perceived latency drops even though total tokens/time is unchanged.
- **Reused async HTTP clients** — one `httpx.AsyncClient` per external service (Tavily, Groq) constructed once at bootstrap and reused, not recreated per request (avoids TCP/TLS handshake cost per call).
- **Short-circuit for simple queries** — if the planner returns exactly 1 query with high confidence, skip the heavier multi-source dedup/rank path (still runs, but on a trivially small set) rather than adding artificial work.
- **Selective full-page fetch** — only top-K sources with thin snippets get fetched; this is the single biggest avoidable latency cost in naive RAG pipelines, so it's opt-in per source, not global.
- **Concurrent RAGAS metrics** — faithfulness / answer relevancy / context precision computed in parallel, not sequentially.

## 4. Token optimization strategies

- **Small model for planning** — the planning prompt + schema is short and doesn't need a 70B model.
- **Hard context token budget** — `ContextBuilder` enforces a fixed budget (e.g. 2,500 tokens) for retrieved context, allocated across sources weighted by rank, truncating lower-ranked snippets first.
- **Dedup before context building** — removing near-duplicate sources means the token budget isn't spent twice on the same fact from two URLs.
- **Snippets over full pages by default** — a snippet is ~30–60 tokens; a full page can be 1,000+. Full-fetch is the exception, gated by the thin-snippet rule (1.3 above).
- **Citation-by-index, not by URL, in the generation prompt** — sources are labeled `[1]`, `[2]`... in the prompt and the model cites indices; full URLs are attached in the response assembler, not repeated in every prompt token.
- **No chat-history replay into search/planning by default** — for a single-turn research question this doesn't matter; noted here because it becomes relevant the moment multi-turn is added (see Future Scalability Ideas, §8, below) — history should be summarized, not replayed verbatim, to avoid linear token growth per turn.

## 5. Parallel execution strategy

Three distinct concurrency points, each using the right primitive:

1. **Search fan-out** — `asyncio.gather(*[provider.search(q) for q in queries], return_exceptions=True)`. `return_exceptions=True` is deliberate: one failed sub-query must not fail the whole turn.
2. **Content extraction** — fetching/parsing the (few) full pages for thin-snippet sources is I/O + light CPU; run via `asyncio.gather` over async fetches, with parsing (trafilatura) offloaded to a thread pool (`asyncio.to_thread`) since HTML parsing is blocking CPU work.
3. **RAGAS metrics** — the 2–3 reference-free metrics are independent given (question, answer, contexts) and are gathered concurrently rather than computed in RAGAS's default sequential batch mode where avoidable.

Per-call timeouts wrap all three (`asyncio.wait_for`), because an interactive chatbot must never let one slow provider call stall the whole turn indefinitely.

## 6. Error handling strategy

- **Retry with backoff** (via `tenacity`) on transient failures from Tavily and Groq — network errors, 429/5xx — with a small max-attempt count (2–3) so retries don't themselves become the latency problem.
- **Per-stage timeout budgets** — search, generation, and evaluation each get their own timeout; a stage that exceeds it fails independently rather than hanging the turn.
- **Graceful degradation ladder**, not all-or-nothing failure:
  - Some sub-queries fail → proceed with whatever results returned (as long as ≥1 succeeded).
  - All search fails → tell the user search is unavailable rather than silently answering ungrounded (never let Groq quietly answer from parametric memory and present it as sourced).
  - RAGAS fails or times out → return the answer with `evaluation: null` + a logged warning, never block the answer on it.
  - Groq generation fails after retries → surface a clear "couldn't generate an answer, please retry" rather than a stack trace.
- **Typed exceptions per layer** (`SearchProviderError`, `LLMGenerationError`, `EvaluationError`) caught at the `ChatPipeline` boundary, logged with a per-turn correlation ID, translated into a single well-shaped error response for the presentation layer.
- **Input validation at the boundary** — empty/absurdly long user input rejected before it reaches the planner, not after burning an LLM call.

## 7. Caching opportunities

| Cache | Key | TTL | Value |
|---|---|---|---|
| Query plan cache | Normalized user query (lowercased, whitespace-collapsed) | Short (e.g. 10 min) | Same question asked twice in a session skips a planning LLM call entirely |
| Search result cache | Individual sub-query string | Medium (e.g. 1 hr) | Different users/turns generating an overlapping sub-query (very common — "best X in Pune" style queries repeat sub-query phrasing) reuse Tavily results, saving both latency and API quota |
| Final answer cache | Hash of (query + context source set) | Optional, short TTL | Risk of staleness for time-sensitive queries — only worth adding if demo shows repeat questions matter |

Start with `InMemoryCache` (simple dict + TTL, fine for a single-process CLI
demo); the `Cache` port means swapping in Redis for a multi-instance API
deployment later is a bootstrap-level config change, not a code change
anywhere else.

## 8. Future scalability ideas

- **Multi-provider fan-out** — a `CompositeSearchProvider` implementing the same `SearchProvider` interface that queries Tavily + Serper together and merges results, with zero changes to anything above it.
- **Semantic cache** — embed incoming queries and check a vector store for near-duplicate past queries before re-planning/re-searching, catching paraphrases that exact-string caching misses.
- **Multi-turn conversation memory** — summarized rolling history feeding the planner, so follow-up questions ("what about Mumbai instead?") inherit context without replaying full transcripts.
- **Embedding/cross-encoder reranker** — drop-in replacement for the heuristic `Ranker` once accuracy needs outgrow it.
- **Streaming end-to-end over SSE/WebSocket** once the FastAPI layer exists.
- **Observability** — structured tracing per turn (OpenTelemetry or a lighter LLM-specific tracer) covering per-stage latency and token counts, feeding a dashboard — valuable for an internship demo that shows *why* the system is fast, not just that it works.
- **Offline eval harness** — a curated (question, reference answer) set run through RAGAS's full metric suite including `context_recall`, run in CI, separate from the live reference-free path.
- **Auth + rate limiting** once exposed as an API beyond local/demo use.
