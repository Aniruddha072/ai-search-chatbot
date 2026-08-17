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

### Decision 6.1

Date: 2026-08-09

Implemented:
`AnswerGenerator` does not catch LLM failures with a fallback the way
`QueryPlanner` does - a timeout or API error propagates to the caller.

Reason:
- There's no safe fallback answer possible without a successful LLM
  call, unlike planning's "just search the raw question." Deciding the
  user-facing behavior on failure is explicitly a Phase 7 (`ChatPipeline`)
  / Phase 10 (resilience) concern per the existing degradation ladder in
  this doc's §6, not this component's job.

### Decision 6.2

Date: 2026-08-09

Implemented:
Streaming is deferred to Phase 11, despite the roadmap checklist's
literal "streaming-capable" wording for this phase.

Reason:
- `AnswerGenerator` needs the complete response regardless - citation
  parsing can't operate on a partial stream.
- Building streaming now would mean designing it with no real consumer
  to validate against until the CLI (Phase 11) exists to actually print
  tokens as they arrive.

✅ *Implemented in Phase 11, exactly as deferred here - see Decisions
11.1-11.4 for how the "citation parsing needs the complete text"
tension above was resolved (a `StreamedAnswer` wrapper, not a bare
generator).*

### Decision 6.3

Date: 2026-08-09

Implemented:
Citation parsing is defensive: duplicate citations of the same source
are deduplicated, and a hallucinated out-of-range index (e.g. `[99]`
when only 2 sources exist) is silently dropped rather than raising.

Reason:
- Matches the project's general pattern of not trusting a single
  validation point (see Decision 5.4) - the LLM's output is treated as
  untrusted input, not assumed well-formed.

### Decision 7.1

Date: 2026-08-09

Implemented:
`ChatPipeline` depends on the `Ranker` interface but on the concrete
`QueryPlanner`/`SearchOrchestrator`/`Deduplicator`/`ContextBuilder`/
`AnswerGenerator` classes directly, not interfaces for all six.

Reason:
- Matches the architecture doc's component table: `Ranker` is the only
  one of these six with a named future alternative (embedding rerank).
  Depending on concretions where no second implementation is planned
  isn't a DIP violation, just accurate.

### Decision 7.2

Date: 2026-08-09

Implemented:
`build_chat_pipeline()` is a plain function, not wrapped in
`@lru_cache` the way `get_settings()` is.

Reason:
- `get_settings()` is called from many places and genuinely needs
  memoization. `build_chat_pipeline()` has exactly one natural call
  site per process (a future CLI's startup) - the caller holds the
  single `ChatPipeline` instance, so there's nothing to cache.

### Decision 7.3

Date: 2026-08-09

Implemented:
`ChatPipeline.handle()` has no try/except and no degradation ladder -
`AnswerGenerator`'s propagated failures (Decision 6.1) bubble straight
out uncaught.

Reason:
- "Catch and translate exceptions at ChatPipeline boundary" and "the
  degradation ladder" are explicit Phase 10 checklist items, not
  Phase 7's. Building them now would be speculative ahead of the
  phase that actually owns this concern.

### Decision 8.1

Date: 2026-08-09

Implemented:
`ragas==0.4.3` is installed via `pip install --no-deps` plus its real
dependencies listed explicitly in `pyproject.toml`. `ragas` itself is
deliberately absent from the normal dependency list; README documents
the extra manual install step.

Reason:
- `ragas` has a hard, unconditional dependency on `scikit-network` (a
  C-extension graph library) with zero prebuilt Windows wheels for any
  Python version - confirmed by probing 3.12/3.13/3.14 explicitly, not
  assumed. Static analysis of the wheel's source confirmed
  `scikit-network` is only imported by `ragas/testset/graph.py`
  (synthetic testset generation), never by anything the evaluation
  code path touches.
- Chosen over installing Visual C++ Build Tools (which would let it
  build normally) because it requires no system-level change, for a
  dependency this project doesn't use anyway.

### Decision 8.2

Date: 2026-08-09

Implemented:
`AnswerRelevancy` is dropped from scope entirely - only `Faithfulness`
and `ContextPrecisionWithoutReference` are wired.

Reason:
- `AnswerRelevancy` requires an embeddings model (confirmed via its
  `MetricWithEmbeddings` base class). Groq doesn't serve one - verified
  directly with a real `client.embeddings.create(...)` call, which
  404s with `model_not_found`, not assumed from the model list alone.
- Adding an embeddings provider (local `sentence-transformers` or a
  paid API) just for one of three metrics would introduce a new
  dependency category for a project deliberately scoped to Tavily +
  Groq only.

### Decision 8.3

Date: 2026-08-09

Implemented:
`Answer` gained an `evaluation: EvaluationResult | None = None` field
(a Phase 1 entity extended), rather than changing
`ChatPipeline.handle()`'s return type to a tuple.

Reason:
- Keeps `handle() -> Answer` consistent with how the roadmap describes
  it throughout every phase - the answer now optionally carries its
  own score, rather than introducing a second return shape this late.
- Defaults to `None`, so every prior phase's `Answer(...)` construction
  keeps working unchanged.

### Decision 8.4

Date: 2026-08-09

Implemented:
Evaluation is scored against the *full* source set `ContextBuilder`
produced, not `answer.sources` (the subset the model actually cited).

Reason:
- Scoring faithfulness/context-precision against a model's own
  self-reported citations would be circular - it would only ever be
  graded against the evidence it chose to show. Verified with a
  dedicated test asserting a source the model never cited was still
  passed to evaluation.

### Decision 8.5

Date: 2026-08-09

Implemented:
`RagasEvaluator` does not reuse the shared `GroqClient`/`AsyncGroq`
instance from Decision 7.1's "reused client" optimization.

Reason:
- `instructor.from_provider(...)` builds its own client via its own
  construction path - there's no shared instance to pass in here.
  Noted explicitly as a real limitation rather than silently diverging
  from the established pattern without explanation.

### Decision 9.1

Date: 2026-08-09

Implemented:
`bootstrap.py` constructs two separate `InMemoryCache()` instances -
one for query plans, one for search results - rather than one shared
cache.

Reason:
- A raw user question could in principle collide with a generated
  sub-query string. A shared cache keyed by that same string would
  return the wrong *type* of cached value (`Query` where
  `list[SearchResult]` was expected, or vice versa). Two cheap,
  separate instances avoid this by construction, with no key-prefixing
  convention needed.

### Decision 9.2

Date: 2026-08-09

Implemented:
`cache: Cache` is a required constructor parameter on both
`QueryPlanner` and `SearchOrchestrator`, not `Cache | None = None`.

Reason:
- Every other collaborator in this codebase (`SearchProvider`,
  `LLMProvider`, `ContentExtractor`, `Evaluator`) has been a required,
  non-optional constructor param. Making this one optional-with-a-
  None-escape-hatch would be the one inconsistent exception, even
  though it meant updating more existing call sites
  (`bootstrap.py` and four test files) than a typical phase touches.

### Decision 9.3

Date: 2026-08-09

Implemented:
`QueryPlanner` only writes a *successful* plan to cache - the fallback
`Query` built on LLM failure is never cached.

Reason:
- Caching the fallback would let a single transient LLM failure poison
  every identical question asked again within the TTL window with a
  degraded single-query plan, even after Groq recovers. Verified with
  a dedicated test that a failing LLM is retried on every call, not
  cached after the first failure.

### Decision 9.4

Date: 2026-08-09

Implemented:
`SearchOrchestrator`'s cache key is `(normalized sub-query,
max_results)`, not just the sub-query text.

Reason:
- Omitting `max_results` would let a cache entry written for one
  result count silently satisfy a request for a different one -
  returning too few (or padding-worthy-of-more) results without any
  error. Costs nothing to include, closes a real correctness gap.

### Decision 9.5

Date: 2026-08-09

Implemented:
`InMemoryCache` has no lock, no eviction policy, and no size cap.

Reason:
- Matches decisions.md §7's own framing: "fine for a single-process
  CLI demo." No `await` occurs inside `get`/`set`, so concurrent
  `asyncio.gather` callers can't interleave mid-operation even without
  a lock - the one accepted gap is a same-key "cache stampede" (two
  concurrent misses both doing the underlying work), a missed
  optimization, not a correctness bug. Revisiting unbounded growth is
  deferred until Phase 11/14 make the process long-running, at which
  point the `Cache` port already makes swapping in Redis a config
  change, not a rewrite.

### Decision 10.1

Date: 2026-08-10

Implemented:
A new `src/domain/exceptions.py` defines `PipelineError` and three
subtypes (`SearchProviderError`, `LLMGenerationError`,
`EvaluationError`), one per infrastructure port. Every adapter
(`TavilyProvider`, `GroqClient`, `RagasEvaluator`) now catches the raw
SDK-specific exception and re-raises the matching typed one, instead of
letting `tavily`/`groq`/`ragas` exception types leak past the adapter
boundary.

Reason:
- Same anti-corruption-layer reasoning already applied to *data*
  (Phase 2's raw-Tavily-dict -> `SearchResult` translation), now applied
  to *errors*. Callers upstream of the adapters never need to know or
  import a third-party exception type.
- Placed in `domain/`, not `infrastructure/`, alongside the ports they
  correspond to - framework-agnostic, zero external dependencies,
  consistent with everything else that lives there.

### Decision 10.2

Date: 2026-08-10

Implemented:
Retry-worthy exception sets were verified against real SDK source
before being wired into `tenacity`, not guessed: Groq's
`APIConnectionError`, `RateLimitError`, `InternalServerError` retry;
`AuthenticationError`/`BadRequestError`/etc. do not. Tavily's own
`TimeoutError` plus `httpx.TransportError` retry (Tavily's client uses
`httpx` internally); `BadRequestError`/`InvalidAPIKeyError`/
`UsageLimitExceededError` do not.

Reason:
- Retrying a non-transient failure (bad API key, malformed request)
  wastes the entire attempt budget on something that will never
  succeed, and delays the user-visible failure for no benefit.
  `tenacity`'s `retry_if_exception_type` makes the selective set
  explicit and testable rather than an implicit "retry everything."

### Decision 10.3

Date: 2026-08-10

Implemented:
`max_retry_attempts` and `retry_backoff_seconds` are `Settings` fields
(env-configurable), not constructor-level constants baked into
`TavilyProvider`/`GroqClient`.

Reason:
- Same category as the existing timeout settings (`search_timeout_seconds`,
  `llm_timeout_seconds`, etc.) - they affect external-call cost and
  latency and are worth tuning per-environment without a code change.
  Contrast with Phase 3's ranking-heuristic constants, which stayed as
  plain constructor defaults because they're internal tuning, not
  external-call-affecting.

### Decision 10.4

Date: 2026-08-10

Implemented:
`ChatPipeline.handle()` always returns an `Answer`, and never raises -
three new branches (invalid input, zero sources after search, answer
generation failure) each return a synthetic `Answer` with
`evaluation=None` instead of propagating an exception to the caller.

Reason:
- Consistent with the self-contained-failure-handling pattern
  `QueryPlanner` (Phase 5) and `EvaluationService` (Phase 8) already
  established - a caller of `ChatPipeline` should never need a
  try/except around `handle()`. `evaluation is None` is reused
  (Phase 8's field, no new field added) to structurally distinguish a
  synthetic/degraded message from a real generated-and-evaluated
  answer, since only a successfully generated `Answer` ever reaches
  `EvaluationService`.

### Decision 10.5

Date: 2026-08-10

Implemented:
Existing broad `except Exception` catches in `QueryPlanner`,
`EvaluationService`, and `SearchOrchestrator` were left broad, not
narrowed to `except PipelineError`. The new typed exceptions add value
through precise retry targeting and clearer logs/messages, not through
narrower catch clauses.

Reason:
- Narrowing those catches to `PipelineError` would let a genuinely
  unexpected bug (a real programming error, not a provider failure)
  propagate uncaught from what's meant to be a defense-in-depth
  boundary. Broad catches there were already a deliberate choice, not
  an oversight to "fix" this phase.

### Decision 10.6

Date: 2026-08-10

Implemented:
`RagasEvaluator` wraps failures as `EvaluationError` but does not retry
them - no `tenacity` wiring, unlike `TavilyProvider`/`GroqClient`.

Reason:
- `EvaluationService` (Phase 8, Decision 1.6) already treats every
  evaluation failure as non-fatal and non-blocking with its own
  timeout - retrying inside the adapter would just delay a result the
  caller is already prepared to receive as "null score," for no
  correctness benefit.

### Decision 10.7

Date: 2026-08-10

Implemented:
The Phase 9-deferred Tavily relative-URL finding (`url='/goto?url=...'`
instead of an absolute URL) is fixed inside `TavilyProvider.search()` -
results whose `url` doesn't start with `http://`/`https://` are
dropped before the method returns.

Reason:
- `TavilyProvider` is already the one file that owns "translate
  Tavily's raw response shape into something the rest of the pipeline
  can trust" (Phase 2). A relative/malformed URL is exactly that kind
  of raw-shape problem, not a resilience concern for `ChatPipeline` to
  handle. Honors the explicit plan recorded in Phase 9's build log to
  address this in Phase 10.

### Decision 11.1

Date: 2026-08-10

Implemented:
Streaming is built as a `StreamedAnswer` wrapper object around
`LLMProvider.generate_stream()`'s async generator, not a bare async
generator function returning the final `Answer` itself.

Reason:
- Verified before writing any code: an `async def` function containing
  `yield` can only `return` with no value - `return some_value` inside
  an async generator is a `SyntaxError`. Citation parsing needs the
  *complete* answer text, which a partial stream can't provide, so
  something has to hold the accumulated text until the stream is
  exhausted and then build the `Answer` from it. `StreamedAnswer` is
  that something: iterating it yields chunks as they arrive (for
  printing), and `build_answer()` afterward parses citations from what
  accumulated - one Groq call, not two.

### Decision 11.2

Date: 2026-08-10

Implemented:
`GroqClient.generate_stream()`'s retry only wraps *acquiring* the
stream (the `chat.completions.create(..., stream=True)` call itself),
never iteration over already-yielded chunks. A failure mid-stream
raises `LLMGenerationError` immediately, not retried.

Reason:
- Once a chunk has been yielded to a caller that may already have
  printed it to a terminal, silently retrying and re-yielding from the
  start would duplicate visible output the user already saw. This is a
  deliberate asymmetry with Phase 10's retry policy for `generate()`/
  `generate_structured()`, where nothing is visible to anyone until the
  full response returns.

### Decision 11.3

Date: 2026-08-10

Implemented:
Each chunk wait in `StreamedAnswer.__aiter__()` is individually
timeout-bounded (reusing the existing `llm_timeout_seconds` /
`AnswerGenerator._timeout_seconds` budget), rather than the whole
stream sharing one fixed overall timeout.

Reason:
- An overall timeout would cut off a long-but-healthy answer the same
  way a stalled connection would, since streaming delivers the same
  total content incrementally instead of all at once. Bounding the gap
  between chunks instead means a stream that keeps producing chunks
  within that window can run for as long as the answer genuinely takes;
  only an actual stall counts as a timeout. Needed no new `Settings`
  field - the existing per-call LLM timeout budget already means the
  right thing here.

### Decision 11.4

Date: 2026-08-10

Implemented:
`ChatPipeline.handle_streaming()` does not catch a generation failure
the way `handle()`'s try/except does. `_prepare()` (validation, zero-
sources) is shared and degrades identically in both methods, but once
`AnswerGenerator.generate_streaming()`'s stream starts being consumed,
a failure propagates to the caller uncaught.

Reason:
- `handle()` can safely swap in a fixed "having trouble generating an
  answer" message because nothing has been shown to the user yet - the
  whole response arrives at once or not at all. `handle_streaming()`
  has no equivalent safe move: by the time a mid-stream failure occurs,
  some of the real answer may already be visible wherever the caller is
  printing it, so there's nothing honest left to silently replace it
  with. Matches the original pre-Phase-10 reasoning for why
  `AnswerGenerator` itself doesn't catch its own failures (Decision
  6.1) - deciding what the user sees on failure belongs to whichever
  layer actually knows what's already been shown, and for a live
  stream, that's the presentation layer (`cli.py`), not `ChatPipeline`.

### Decision 11.5

Date: 2026-08-10

Implemented:
`EvaluationService`'s caught-exception handling falls back to
`type(exc).__name__` when `str(exc)` is blank, and `cli.py`'s
`_print_evaluation()` checks `evaluation.error is not None` rather than
a truthy check.

Reason:
- Found via live dogfooding, not a design review: a real evaluation
  timeout from `asyncio.wait_for` raises a bare `TimeoutError()`, whose
  `str()` is empirically `''` (verified directly against the real
  exception, not assumed). That blank string flowed into
  `EvaluationResult.error`, which is falsy - so `_print_evaluation`'s
  original `if evaluation.error:` check silently treated a genuine
  failure as if none had occurred, printing nothing at all. Both the
  log line and the CLI display were undiagnosable from the same root
  cause. Fixed at both layers rather than just one, since any
  `Evaluator` implementation could plausibly raise a blank-message
  exception, and the display layer shouldn't have to trust that every
  failure includes one.

### Decision 11.6

Date: 2026-08-10

Implemented:
`presentation/cli.py`'s Ctrl-C handling moved from two in-coroutine
`try/except KeyboardInterrupt` blocks inside `main()` to a single
`except KeyboardInterrupt:` wrapping `asyncio.run(main())` itself, in a
new `run()` function.

Reason:
- Found via live dogfooding, then root-caused from a real production
  traceback rather than guessed at: the exception delivered into
  `main()`'s coroutine at its current await point is
  `asyncio.CancelledError`, not `KeyboardInterrupt` - `asyncio.run()`
  cancels the running task on interrupt, and only *afterward*
  re-raises the actual `KeyboardInterrupt` from its own top-level
  frame (documented CPython 3.11+ `asyncio.Runner` behavior), after
  `main()` has already been torn down. No `try/except` placed
  anywhere inside `main()`'s own coroutine can catch an exception
  raised by a different, outer function once that coroutine no
  longer exists - the old handlers were structurally incapable of
  ever catching it, not just unlucky. Tracked as GitHub issue #2
  (closed): a real interactive-terminal reproduction confirmed the
  crash, though 14 automated `CTRL_C_EVENT` reproduction attempts
  (piped stdin, then a genuine new Win32 console) never triggered the
  underlying timing-dependent race - the fix was verified via a
  deterministic regression test forcing the exact mechanism, plus the
  user's own live Ctrl-C confirmation against the fix.

---

### Decision 12.1

Date: 2026-08-11

Implemented:
`pytest-cov` added as a real dev dependency (`pyproject.toml`), and used
to audit actual statement coverage before deciding Phase 12's scope,
rather than assuming "a test file exists per module" already meant the
module was covered.

Reason:
- The audit found every `domain/`, `application/`, and `infrastructure/`
  module already at 100% coverage incidentally, but surfaced two real,
  previously-untested branches in `ranker.py` (the empty-query-terms
  divide-by-zero guard, and the future-published-date branch) and a
  meaningful, closeable gap in `cli.py` beyond its accepted
  interactive-only surface (`_print_sources`'s non-empty/empty paths,
  `_handle_turn`'s happy path and its mid-stream-exception path, and
  `_read_line` itself via a monkeypatched `input`) - none of these
  needed real stdin/process interaction to test, contradicting
  `test_cli.py`'s prior docstring claim that none of `cli.py` was
  unit-testable. Coverage measurement turned "which tests should we
  add" from a guess into a checklist. `main()`'s own loop and the
  `if __name__ == "__main__":` guard remain intentionally
  manual-smoke-test-only - they need real stdin/process wiring the way
  `run()`'s Ctrl-C path already did (Decision 11.6).
- Also used to re-verify the gated integration suite live
  (`RUN_INTEGRATION_TESTS=1`, 7/7 passed), including a real
  `test_real_ragas_evaluator_scores_a_grounded_answer` success (valid
  Faithfulness/ContextPrecision scores, `error is None`, ~14.5s
  runtime) - resolving the live-RAGAS-verification item deferred
  earlier this session. That ~14.5s runtime, close to
  `evaluation_timeout_seconds`'s 15s budget even with zero rate-limit
  retries, is itself the explanation for why this morning's live CLI
  attempts timed out: RAGAS evaluation is inherently near-budget, so
  any 429 backoff on top reliably exceeds it. Not a code bug - an
  external rate-limit/timeout-margin reality, consistent with the
  earlier decision not to touch the evaluation implementation.

---

### Decision 12.2

Date: 2026-08-11

Implemented:
`evaluation_timeout_seconds` raised from 15.0 to 30.0 (`settings.py`,
`.env.example`). Nothing else about the evaluation architecture changed -
same Groq/RAGAS wiring, same unwrapped `RagasEvaluator` client
(Decision 8.5), no provider switch.

Reason:
- Decision 12.1's real integration run measured a *successful* RAGAS
  evaluation at ~14.5s with zero rate-limit retries - the old 15s
  budget was too tight for the happy path alone, before any 429 backoff
  gets added on top. A model/provider swap was considered and rejected:
  probed real rate-limit headers for both Groq models and found
  `llama-3.1-8b-instant` (6,000 TPM) has *less* per-minute headroom than
  the `llama-3.3-70b-versatile` model `RagasEvaluator` already uses
  (12,000 TPM) - switching would have made the timeout problem worse,
  not better. Widening the timeout is a one-line config change that
  fixes the actual measured margin problem without adding a new
  provider or redesigning the evaluator just to work around a free-tier
  limit.

---

### Decision 13.1

Date: 2026-08-11

Implemented:
`ChatPipeline` records per-stage wall-clock durations (planning, search,
context, generation, eval) into a `dict[str, float]` via a small
`_timed()` helper, and logs one `turn timings: ... total=Xs` INFO summary
line at the true end of every turn - success, or any degradation point
(invalid input, zero sources, generation failure) - reporting whatever
stages actually ran.

Reason:
- Matches the roadmap's exact scope (`planning/search/context/
  generation/eval durations`) without adding new pipeline stages or
  failure modes - purely additive instrumentation.
- `handle_streaming()`'s "generation" duration can't be measured by
  wrapping a single awaitable the way the other four stages are,
  because token generation happens as the caller iterates the stream,
  not inside one call `ChatPipeline` controls. `PipelineStream.streaming()`
  instead starts a timer when the stream is handed to the caller and
  stops it inside `finalize()` (once `get_answer()` is called after full
  consumption) - an honest measure of what the user actually waited for,
  at the cost of also including the caller's own per-chunk I/O
  (printing to a terminal), not just the Groq call itself.
- If a stream fails mid-consumption (Decision 11.4 - propagates
  uncaught, by design), the timing summary never fires, since
  `finalize()` is never reached. Left as a known gap rather than adding
  complexity to catch it: `cli.py` already logs a `streaming turn
  failed: %s` warning for that case, so the failure isn't silent, just
  without a stage breakdown.
- Degraded/early-exit turns still log a summary (with fewer stages
  present) rather than skipping the log line entirely - observability
  should reflect real behavior including degraded turns, not just the
  happy path.

---

### Decision 13.2

Date: 2026-08-11

Implemented:
`configure_logging()`'s handler now writes to `stderr`, not `stdout`.

Reason:
- Closes the cosmetic gap noted in Phase 11 (`phase11.md`): `presentation/
  cli.py` prints the streamed answer to `stdout`, and the previous
  shared-stdout handler meant log lines (Groq/Tavily HTTP request logs,
  `instructor`'s own logs) interleaved with the prompt and output. Never
  landed *inside* streamed tokens (nothing touched logs mid-stream), so
  it was noise, not a correctness bug - but still worth fixing once
  Phase 13 made observability output (the new turn-timing summary line)
  something worth keeping clean and separable.
- One line. Both streams still land in the same terminal by default, so
  nothing about the interactive experience changes - but `stdout` can
  now be redirected/piped independently to get just the answer text,
  and `stderr` independently to get just structured logs. Verified live:
  a real CLI run with `stdout`/`stderr` captured to separate files
  showed clean answer text with zero log lines on `stdout`, and the new
  `turn timings: ...` line correctly on `stderr`.

---

### Decision 13.3

Date: 2026-08-11

Implemented:
`Settings.log_level`'s default changed from `"INFO"` to `"CRITICAL"`
(`settings.py`, `.env.example`).

Reason:
- Decision 13.2 made logs and answer text *separable* streams, but did
  nothing about the terminal a real user actually sees by default -
  stdout and stderr both still print to the same window unless
  explicitly redirected, so the CLI's default experience was unchanged:
  every HTTP request log, the new turn-timing summary, and internal
  warning/error messages still appeared mixed into the conversation.
  Live dogfooding surfaced this directly: "I want it to look like a
  genuine chatbot that answers to my questions" - not a dev console.
- Audited every first-party log call before picking the new default:
  every `logger.info`/`logger.warning` in the codebase covers a
  condition the CLI *already* renders cleanly to the user through its
  own output (an evaluation-unavailable note, a generation-failure
  notice, the degraded-answer text itself - exact wording refined
  further in Decision 13.4) - the raw log line is pure duplication for
  an end user, never new information. The one `ERROR`-level line ever
  observed came from a third-party library (`instructor`'s own
  retry-exhaustion log), not this codebase. No `logger.critical()` call
  exists anywhere, in this project or its dependencies as observed - so
  `CRITICAL` is, in practice, silent under every condition tested,
  including a real live failure (a generation call failing mid-turn
  from Groq's daily quota still cooling down) - verified live: the
  terminal showed only the CLI's own degraded-turn message, no log line
  at all.
- Fully reversible per-run, not a capability removed: `LOG_LEVEL=INFO`
  in `.env` restores every log Phase 13 added (turn timings, HTTP
  request logs) for anyone debugging - the default just stops assuming
  a developer is always the one watching the terminal.

---

### Decision 13.4

Date: 2026-08-11

Implemented:
Two user-facing degraded-turn messages reworded in `presentation/cli.py`:
`_print_evaluation`'s error branch went from printing the raw
`evaluation.error` string to a fixed `"(scores unavailable for this
answer)"`; `_handle_turn`'s mid-stream-exception branch went from
`"[response interrupted by an error]"` to `"[I ran into a problem while
answering. Please try again later.]"` (also applied to the matching
non-streaming message in `pipeline.py`'s `handle()`, for the same
reason). "Later," not just "again" - an immediate retry is likely to
hit the exact same transient condition (e.g. a rate limit) that just
failed.

Reason:
- `Decision 11.5` made sure an evaluation failure was never silently
  swallowed, but the literal text it chose to surface was always the
  raw exception - fine for a developer, not for the target audience of
  a "genuine chatbot" the CLI is meant to be. Direct user feedback: "the
  error messages dont really explain what happened... hand out simple
  errors, but not too dumb-sounding."
- The full technical detail was never actually lost by this change -
  it was already flowing into `EvaluationResult.error` and
  `EvaluationService`'s own warning log the whole time; Decision 13.3
  already made that log opt-in via `LOG_LEVEL=INFO` rather than
  default-visible. This decision only changes what's printed directly
  into the conversation, matching the tone `pipeline.py`'s existing
  degraded messages already used ("I'm having trouble generating an
  answer right now...") rather than inventing a new voice.
- Verified live: a real turn with a failed evaluation (Groq rate limit)
  printed `(scores unavailable for this answer)` with no technical
  detail, while the answer itself and its sources rendered normally.

---

### Decision 14.1

Date: 2026-08-12

Implemented:
Phase 14's public demo hosting chosen as Streamlit Community Cloud
(`src/presentation/streamlit_app.py`, root `requirements.txt`), not the
originally-selected Gradio + Hugging Face Spaces.

Reason:
- Gradio + HF Spaces was the initial recommendation and was explicitly
  selected before any implementation started. Before building anything,
  HF's current docs were checked live (this project's standing rule:
  verify real external behavior before designing around it) - and found
  that creating a Gradio or Docker Space now requires a paid PRO plan on
  a personal account; free accounts can only run pre-existing Spaces on
  ZeroGPU, not create new Gradio ones. This directly conflicted with the
  explicit "I do not want to spend any money" requirement.
- Streamlit Community Cloud was verified live (streamlit.io/cloud) as
  free for public apps deployed from a GitHub repo, no card on file
  mentioned - and its own `st.write_stream()`/`st.chat_input`/
  `st.chat_message` primitives map onto this project's existing
  `PipelineStream` (async iterator of text chunks) closely enough that
  no real adapter layer was needed beyond the presentation-layer file
  itself (see Decision 14.3 for where that mapping wasn't as direct as
  first assumed).
- This was caught and corrected *before* any Gradio-specific code was
  written, not discovered mid-implementation - the same
  verify-before-building discipline this project has applied to every
  other external integration (Tavily's relative-URL results, Groq's
  real rate-limit headers, RAGAS/instructor's actual client
  construction API, etc).

---

### Decision 14.2

Date: 2026-08-12

Implemented:
`infrastructure/evaluation/null_evaluator.py`: a no-op `Evaluator`
returning `EvaluationResult()` instantly, no I/O. `bootstrap.py` split
into a private `_build_pipeline(settings, evaluator)` helper plus two
public entry points - `build_chat_pipeline()` (unchanged: real
`RagasEvaluator`, used by the CLI) and `build_demo_pipeline()` (new:
`NullEvaluator`, used by the Streamlit demo).

Reason:
- The public demo must not run RAGAS on every request: RAGAS makes
  several extra Groq LLM-judge calls per answer on top of the ones
  already needed to plan and generate it, adding real latency and, on a
  free-tier account already shown to hit both per-minute and daily
  quota limits during normal development (Decision 12.2), a real risk
  that one visitor's evaluation calls exhaust a shared quota for
  everyone else hitting the public demo.
- `EvaluationService` already treats "no scores" as a normal, expected
  outcome for any evaluator failure (Decision 1.6) - `NullEvaluator`
  produces exactly that outcome on purpose, with no I/O, so nothing
  downstream (`ChatPipeline`, `EvaluationService`, the CLI's own
  `_print_evaluation`-equivalent rendering) needed to change or even be
  aware a different evaluator is in use.
- An optional/defaulted `evaluator` parameter on a single
  `build_pipeline()` function was considered and rejected in favor of
  two explicitly-named functions - consistent with Decision 9.2's
  precedent of explicit required collaborators over implicit defaults.
  A default risks a future caller silently getting (or not getting)
  real RAGAS scores depending on an easy-to-miss default value, rather
  than making the choice obvious at the call site.
- `RagasEvaluator`'s import was moved from module level into
  `build_chat_pipeline()`'s function body (a deliberate, commented
  exception to normal top-of-file imports) - `ragas_evaluator.py`
  imports `ragas`, which the demo's `requirements.txt` deliberately
  excludes. A module-level import would have made importing
  `bootstrap.py` itself require `ragas` to be installed, breaking
  `build_demo_pipeline()`/the whole Streamlit app even though it never
  touches `RagasEvaluator` - caught before it could ship as a broken
  Streamlit Cloud deploy, by checking what `requirements.txt`
  deliberately leaves out against what `bootstrap.py` actually imports.

---

### Decision 14.3

Date: 2026-08-12

Implemented:
`streamlit_app.py` builds a fresh `build_demo_pipeline()` inside every
single per-turn `asyncio.run()` call - never cached across turns via
`st.cache_resource` - and streams tokens by hand (iterating the chunks
and updating a `st.empty()` placeholder) rather than passing
`PipelineStream` to `st.write_stream()` directly.

Reason:
- Verified live, with a minimal reproduction, before writing the real
  app code: an `httpx.AsyncClient` (which `GroqClient`/`TavilyProvider`
  both use, directly or via their SDKs) reused across two separate
  `asyncio.run()` calls raises `RuntimeError: Event loop is closed` on
  the second call - `asyncio.run()` tears its event loop down when it
  returns, and the client's connection pool is bound to whichever loop
  was running when it was first used. A cached pipeline (`st.
  cache_resource`) plus one `asyncio.run()` per Streamlit rerun - the
  natural-looking design - would crash on a session's *second*
  question, not the first, making it easy to ship without noticing in
  a quick one-question smoke test.
- The fix verified as sufficient: fresh clients constructed and used
  entirely inside one `asyncio.run()` call, repeated per turn, complete
  cleanly across repeated calls with no crash - confirmed both with an
  isolated `httpx` reproduction and live, via two real consecutive
  questions through the actual running Streamlit app.
- Leaving each turn's clients unclosed for garbage collection (rather
  than adding `close()`/`aclose()` methods to `GroqClient`/
  `TavilyProvider` just for this one caller) was verified live not to
  raise or warn - consistent with the CLI's own model of relying on
  process exit rather than explicit resource lifecycle management, and
  avoiding scope creep into already-shipped, already-tested
  infrastructure classes for a phase explicitly scoped to stay simple.
- `st.write_stream()` was the original plan (Decision 14.1's note that
  it maps onto `PipelineStream` closely) - but its own internal
  async-to-sync conversion (`type_util.async_generator_to_sync`) spins
  up a *separate*, brand-new event loop to consume whatever async
  generator it's given, which would cross loops with whatever loop
  `handle_streaming()`'s planning/search stages already ran under - the
  exact same failure mode. It also only accepts a real async generator
  (`inspect.isasyncgen`), not an arbitrary object implementing
  `__aiter__` like `PipelineStream` - a second, independent reason it
  couldn't be passed directly. Manually iterating inside the turn's own
  `asyncio.run()` call and updating a placeholder avoids both problems
  at once, at the cost of `st.write_stream()`'s built-in typewriter
  animation - chunks still render progressively as they arrive, just
  without the character-reveal effect.
- This also means the demo loses the CLI's cross-turn `InMemoryCache`
  benefit within one browser session (a fresh pipeline means fresh,
  empty query-plan/search-result caches every turn) - an accepted,
  deliberate tradeoff for a low-traffic public demo, not something
  worth a custom persistent-event-loop workaround for the sake of a
  cache hit on a repeated identical question.

### Decision 15.1

Date: 2026-08-13

Implemented:
Reference resolution for follow-up questions ("which one", "its") folded
into `QueryPlanner.plan()`'s existing Groq call via a new optional
`conversation: ConversationContext | None = None` parameter, rather than
a separate rewrite-the-question LLM call.

Reason:
- Resolving a pronoun against recent context is the same category of
  work `QueryPlanner` already does (deciding what the user actually
  wants before turning it into search queries), not a second, unrelated
  task.
- A dedicated rewrite call is the textbook RAG pattern, but it adds a
  second Groq round-trip on every follow-up turn. Folding resolution
  into the existing call keeps this at zero additional Groq calls per
  turn, with or without conversation history present.
- `conversation` defaults to `None` at every layer it passes through
  (`QueryPlanner.plan()`, `ChatPipeline.handle()`/`handle_streaming()`/
  `_prepare()`), so every existing caller (`cli.py`, every pre-Phase-15
  test) gets byte-identical prompts and cache keys - verified directly
  with a regression test asserting the composed prompt equals the raw
  question when `conversation` is `None`.

### Decision 15.2

Date: 2026-08-13

Implemented:
A bounded sliding window of recent turns (default last 2, via new
`Settings.conversation_history_turns`, `0` disables the feature), not
full conversation history - each window entry is `(question, truncated
answer)`, not just the question. `QueryPlanner`'s cache key now folds in
a digest of the conversation when one is present.

Reason:
- Full history would grow the planning prompt linearly per turn (and
  quadratically over a whole session) - a fixed window keeps prompt
  growth roughly constant no matter how long a conversation runs.
- The entity a follow-up actually needs ("VIT Pune", "cheapest") is
  usually sitting in the *answer*, not the question - each window entry
  stores a truncated answer (300 characters) for exactly this reason,
  not just the question text.
- The pre-existing cache key (`_normalize(user_query)` alone) would let
  two different conversations' identical literal follow-ups ("which one
  is cheapest?") collide and return one conversation's cached plan to
  the other - a real correctness bug, not just a missed optimization.
  Fixed by folding a SHA-256 digest of the conversation into the key
  whenever one is present, while preserving the exact pre-Phase-15 key
  when `conversation is None`.
- `ConversationTurn`/`ConversationContext` were added to
  `domain/entities.py` as plain, immutable dataclasses - the same
  shape/dependency rules `Query`/`Source` already follow, not a new kind
  of thing.

### Decision 15.3

Date: 2026-08-13

Implemented:
Live-verified against real Tavily/Groq (not just mocked unit tests),
running the exact 5-question conversation from the original design
proposal end-to-end through `build_demo_pipeline()`.

Reason:
- Unit tests with a mocked LLM provider can only prove the plumbing
  (conversation gets threaded through, the prompt gets composed, the
  cache key changes) - not whether the real model actually resolves
  references correctly given the updated prompt. That needed a real run.
- All five turns resolved correctly: "which one is cheapest?" correctly
  expanded against every college named in turn 1; "what about its
  placement record?" correctly resolved "its" to the specific college
  turn 2 had identified as cheapest; a later topic-continuation question
  ("What about VIT?") was answered as a sensible comparison against the
  two topics actually present in the (2-turn) window rather than a bare
  restatement, showing the sliding window correctly shifts the effective
  topic forward as older turns age out; the final cutoff question
  correctly resolved against both colleges still in scope at that point.
- `build_conversation_context()` (`src/presentation/conversation_context.py`)
  was deliberately split out of `streamlit_app.py` rather than defined
  inline there - that file runs top-level Streamlit calls on import
  (`st.set_page_config()`, `st.chat_input()`, etc.), so a pure function
  living there couldn't be unit-tested without executing those outside a
  real Streamlit script run. Matches Phase 12's precedent of extracting
  `cli.py` helpers specifically so they're testable in isolation.

### Decision 16.1

Date: 2026-08-17

Implemented:
Both Groq models swapped: `groq_fast_model` from `llama-3.1-8b-instant` to
`openai/gpt-oss-20b`, and `groq_capable_model` from `llama-3.3-70b-versatile`
to `openai/gpt-oss-120b`. Not a roadmap phase, just a maintenance migration
forced by Groq's own deprecation schedule.

Reason:
- Groq is decommissioning both models on August 16, 2026, confirmed by
  reading their own deprecations page (console.groq.com/docs/deprecations)
  directly rather than trusting the shutdown date secondhand - it lists
  `openai/gpt-oss-20b` and `openai/gpt-oss-120b` as the recommended
  replacements for exactly these two models, so this migration takes the
  path Groq itself points to rather than picking a different pair.
- Every hardcoded occurrence of the old model strings in live code and
  tests was grepped and updated: `settings.py` defaults, `.env.example`,
  and the three integration tests that construct a `GroqClient` directly
  with an explicit model name instead of going through `Settings`. Mentions
  inside `docs/decisions.md`'s own earlier entries and the Phase 5/6/12
  build logs were left alone on purpose - they're dated records of what
  was true about the old models at the time, not live configuration, and
  rewriting them would misattribute those findings to models they were
  never run against.
- Verified live against the real Groq API before trusting the swap, not
  just the unit suite (which mocks the LLM provider and can't catch a
  model-specific quirk): `generate_structured()` against
  `openai/gpt-oss-20b` returned a valid `QueryPlanResponse` in about a
  second, and `generate_stream()` against `openai/gpt-oss-120b` streamed
  a real multi-chunk answer end to end. Worth recording as a genuine
  gotcha check rather than an assumption: this project already hit a real
  structured-output incompatibility once before switching *to* the old
  models (Decision 1.5's phase log, Phase 5 - the old models don't support
  strict `response_format: json_schema`, only the `openai/gpt-oss` family
  does), so there was real reason to worry the reverse direction might
  break something too. It didn't - both new models worked cleanly through
  the existing `json_object` mode with no refusals and no shape
  differences from before.
- All 188 unit tests pass unchanged after the swap - nothing in the
  mocked test suite depended on the literal old model strings except the
  three integration tests already covered above.

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

**1.5 Model tiering on Groq.** ✅ *Fully implemented as of Phase 6 - fast model for planning (Phase 5), capable model for generation (Phase 6).*
Query planning uses a small/fast Groq model (e.g. `llama-3.1-8b-instant`);
final answer generation uses a larger model (e.g. `llama-3.3-70b-versatile`).
Planning is a short structured-output task where the small model is reliable;
answer quality is what the user actually judges, so it gets the bigger model.
This alone is one of the larger latency/cost wins available (the planning
call is 3-5x cheaper and faster than the generation call).

**1.6 RAGAS runs reference-free, synchronously, but non-blocking on failure.** ✅ *Implemented in Phase 8, with one correction: **answer relevancy was dropped** (Decision 8.2) - it requires an embeddings model, and Groq doesn't serve one, verified with a real 404. Faithfulness and context precision run exactly as planned: concurrently, non-blocking on failure.*
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

**1.7 CLI first.** ✅ *Implemented in Phase 11 (`presentation/cli.py`).
Validates the pipeline end-to-end fastest. `ChatPipeline` stayed
presentation-agnostic by construction through Phases 9-10 (caching,
resilience) with zero changes needed to accommodate the eventual CLI -
`handle_streaming()` was the only new surface it needed to add, and
`api.py` remains additive later, not a rewrite.*

---

## 2. Tradeoffs summary

| Decision | Gains | Costs | Mitigation |
|---|---|---|---|
| Single search provider | Simpler, meets constraint, cheaper | Coverage limited to one index | Interface allows swap/fan-out later |
| Snippet-first, selective fetch | Fast, cheap | Occasionally thinner context than full pages | Full-fetch triggers for top-K + short snippets |
| Heuristic ranking (no embeddings) | No extra model/latency/cost | Lower ranking precision than semantic rerank | Ranker port makes upgrade a one-file change |
| Sync RAGAS in the request path ✅ | User sees eval score immediately (per spec) | Adds real latency (RAGAS = more LLM calls) | Parallelize metrics; fail-open (don't block answer) |
| Dropped `answer_relevancy` ✅ | No new embeddings provider needed | Only 2 of 3 originally-planned metrics scored | Faithfulness + context precision still catch the main failure modes |
| LLM-decided query count | Generalizes better than rules | Occasional over/under-generation | Hard cap at 5 in schema; min 1 enforced by validation |
| In-memory cache by default | Zero infra to start | Doesn't survive restarts, not multi-instance | `Cache` port swaps to Redis with one config change |

---

## 3. Performance optimizations

- **Parallel search fan-out** — all sub-queries hit Tavily concurrently via `asyncio.gather`, not sequentially.
- **Model tiering** — small/fast model for planning, larger model only for the user-facing answer.
- **Streaming the final answer** ✅ — the CLI streams the answer token-by-token as it's generated rather than waiting for the full completion, so perceived latency drops even though total tokens/time is unchanged. *(Phase 11; a later FastAPI layer, Phase 14, can expose the same `ChatPipeline.handle_streaming()` over SSE with no pipeline changes.)*
- **Reused async HTTP clients** ✅ — one `GroqClient` (wrapping one `AsyncGroq`) constructed once in `bootstrap.py` and shared between `QueryPlanner` and `AnswerGenerator`, not recreated per request. *(Phase 7 — required no new code, just correct composition-root wiring; see Decision 7.1's phase log.)*
- **Short-circuit for simple queries** — if the planner returns exactly 1 query with high confidence, skip the heavier multi-source dedup/rank path (still runs, but on a trivially small set) rather than adding artificial work.
- **Selective full-page fetch** — only top-K sources with thin snippets get fetched; this is the single biggest avoidable latency cost in naive RAG pipelines, so it's opt-in per source, not global.
- **Concurrent RAGAS metrics** ✅ — faithfulness and context precision computed in parallel via `asyncio.gather` (answer relevancy dropped, Decision 8.2). *(Phase 8)*

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
3. **RAGAS metrics** ✅ — the 2 reference-free metrics actually implemented (Decision 8.2) are independent given (question, answer, contexts) and are gathered concurrently via `asyncio.gather`, not computed in RAGAS's default sequential batch mode. *(Phase 8)*

Per-call timeouts wrap all four points now (search, content-fetch, LLM calls, and evaluation - all ✅), because an interactive chatbot must never let one slow provider call stall the whole turn indefinitely.

## 6. Error handling strategy

- **Retry with backoff** (via `tenacity`) on transient failures from Tavily and Groq — network errors, 429/5xx — with a small, configurable max-attempt count (default 3, `max_retry_attempts`) so retries don't themselves become the latency problem. ✅ *(Phase 10 — Decision 10.2/10.3, exact retry-worthy exception sets verified against real SDK source, not guessed)*
- **Per-stage timeout budgets** ✅ — search, content-fetch, LLM calls, and evaluation each get their own timeout; a stage that exceeds it fails independently rather than hanging the turn.
- **Graceful degradation ladder**, not all-or-nothing failure:
  - Some sub-queries fail → proceed with whatever results returned (as long as ≥1 succeeded). ✅ *(Phase 2)*
  - Empty/absurdly long input → rejected with a clear message before `QueryPlanner` is even called. ✅ *(Phase 10)*
  - Zero sources after search → skip `AnswerGenerator` entirely and return a clear "couldn't find information" message rather than asking Groq to generate from nothing. ✅ *(Phase 10)*
  - RAGAS fails or times out → return the answer with `evaluation: null` + a logged warning, never block the answer on it. ✅ *(Phase 8, `EvaluationService`)*
  - Groq generation fails after retries → `ChatPipeline` catches the failure and returns a fixed "having trouble generating an answer" message instead of propagating. ✅ *(Phase 10)*
- **Typed exceptions per layer** (`SearchProviderError`, `LLMGenerationError`, `EvaluationError`) ✅ — raised by the adapters that own each port (`TavilyProvider`, `GroqClient`, `RagasEvaluator`), *not* narrowly caught at one central `ChatPipeline` boundary: existing broad `except Exception` catches in `QueryPlanner`/`SearchOrchestrator`/`EvaluationService` stay broad by design (Decision 10.5), and `ChatPipeline` only adds a new catch around answer generation specifically, since that's the one failure with no existing self-contained handler. *(Phase 10)*
- **Input validation at the boundary** ✅ — empty/absurdly long user input rejected in `ChatPipeline.handle()` before it reaches the planner, not after burning an LLM call. *(Phase 10, `max_query_length`)*

## 7. Caching opportunities ✅ *Query plan and search result caches implemented in Phase 9, exactly as designed below (search result cache key extended to include `max_results` - Decision 9.4). Final answer cache remains future - it was always framed as optional here.*

| Cache | Key | TTL | Value |
|---|---|---|---|
| Query plan cache ✅ | Normalized user query (lowercased, whitespace-collapsed) | 10 min (`query_plan_cache_ttl_seconds`) | Same question asked twice in a session skips a planning LLM call entirely |
| Search result cache ✅ | Sub-query string + `max_results` (Decision 9.4) | 1 hr (`search_result_cache_ttl_seconds`) | Different users/turns generating an overlapping sub-query (very common — "best X in Pune" style queries repeat sub-query phrasing) reuse Tavily results, saving both latency and API quota |
| Final answer cache | Hash of (query + context source set) | Optional, short TTL | Risk of staleness for time-sensitive queries — only worth adding if demo shows repeat questions matter |

`InMemoryCache` (simple dict + TTL, fine for a single-process CLI demo) is
implemented; the `Cache` port means swapping in Redis for a multi-instance
API deployment later is a bootstrap-level config change, not a code change
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
