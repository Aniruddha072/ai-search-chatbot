# AI Search Chatbot

An interactive research chatbot: dynamic query planning → parallel Tavily
search → dedup/rank → grounded Groq answer → RAGAS evaluation.

Full architecture, design decisions, and the phased roadmap live in
[`docs/`](docs/) — see [`docs/architecture.md`](docs/architecture.md),
[`docs/decisions.md`](docs/decisions.md), and
[`docs/roadmap.md`](docs/roadmap.md). Build notes for each completed phase
are in [`docs/phases/`](docs/phases/); a session-by-session dev journal is
in [`DEVLOG.md`](DEVLOG.md).

An earlier learning prototype (LangChain `create_agent` + Tavily + Gemini)
is preserved as-is in
[`archive/module7-learning-search-agent/`](archive/module7-learning-search-agent/)
for reference; it is not part of the active codebase.

## Architecture

Clean architecture, inner layers depending on nothing outward:

- **`src/domain/`** — entities (`Query`, `SearchResult`, `Source`, `Answer`, `EvaluationResult`) and interfaces (`SearchProvider`, `LLMProvider`, `Ranker`, `Evaluator`, `ContentExtractor`, `Cache`). No I/O, no external libraries.
- **`src/application/`** — orchestration logic that depends only on the interfaces above. `SearchOrchestrator`, `Deduplicator`, `HeuristicRanker`, `ContextBuilder`, `QueryPlanner`, `AnswerGenerator`, `ChatPipeline`, `EvaluationService` implemented; the rest is not yet.
- **`src/infrastructure/`** — concrete adapters (Tavily, Groq, RAGAS, cache) implementing those interfaces. `TavilyProvider`, `TrafilaturaContentExtractor`, `GroqClient`, `RagasEvaluator`, `InMemoryCache` implemented; the rest is not yet.
- **`src/bootstrap.py`** — composition root wiring real Settings-backed instances into one `ChatPipeline`. Implemented.
- **`src/presentation/`** — CLI entry point. Not yet implemented.

Full pipeline diagram and component responsibilities: [`docs/architecture.md`](docs/architecture.md).

## Current Progress

- [x] Phase 0 — Project scaffolding
- [x] Phase 1 — Domain layer
- [x] Phase 2 — Search integration
- [x] Phase 3 — Dedup + ranking
- [x] Phase 4 — Context building
- [x] Phase 5 — Query planning
- [x] Phase 6 — Answer generation
- [x] Phase 7 — Pipeline wiring
- [x] Phase 8 — RAGAS evaluation
- [x] Phase 9 — Caching
- [x] Phase 10 — Resilience hardening
- [x] Phase 11 — CLI presentation
- [ ] Phase 12 — Testing
- [ ] Phase 13 — Observability & polish
- [ ] Phase 14 — Optional: FastAPI layer

## Project Structure

```
src/
├── bootstrap.py           # composition root: Settings -> real instances -> one ChatPipeline
├── domain/
│   ├── entities.py       # Query, SearchResult, Source, Answer, EvaluationResult
│   ├── interfaces.py     # SearchProvider, LLMProvider, Ranker, Evaluator, ContentExtractor, Cache
│   └── exceptions.py     # PipelineError + SearchProviderError, LLMGenerationError, EvaluationError
├── application/
│   ├── search_orchestrator.py  # concurrent fan-out over a SearchProvider, per-query timeout
│   ├── deduplicator.py         # URL normalization + near-duplicate content passes
│   ├── ranker.py               # HeuristicRanker: weighted provider/keyword/recency scoring
│   ├── context_builder.py      # top-K selection, thin-snippet full-fetch, token-budget enforcement
│   ├── query_planner.py        # Groq structured-output call -> Query, with single-query fallback
│   ├── answer_generator.py     # Groq generate()/generate_streaming() -> cited Answer; failures propagate to ChatPipeline
│   ├── pipeline.py             # ChatPipeline: chains query planning through evaluation; handle() + handle_streaming(), always returns Answer
│   └── evaluation_service.py   # non-blocking Evaluator wrapper: timeout + catch, always returns EvaluationResult
├── infrastructure/
│   ├── search/
│   │   └── tavily_provider.py  # implements SearchProvider via Tavily's async client; retries + SearchProviderError + URL filter
│   ├── llm/
│   │   └── groq_client.py      # implements LLMProvider (generate + generate_structured + generate_stream); retries + LLMGenerationError
│   ├── evaluation/
│   │   └── ragas_evaluator.py  # implements Evaluator via RAGAS + instructor + Groq; wraps failures as EvaluationError
│   ├── cache/
│   │   └── memory_cache.py     # InMemoryCache: dict + lazy TTL expiry, implements Cache
│   └── content/
│       └── content_extractor.py  # TrafilaturaContentExtractor implements ContentExtractor
├── config/
│   ├── settings.py       # pydantic-settings, validated env config
│   └── prompts/
│       ├── query_planner.txt       # system prompt text, plain text, not Python
│       ├── query_planning.py       # loads the .txt + QueryPlanResponse schema
│       ├── answer_generation.txt   # cite-or-refuse system prompt, plain text
│       └── answer_generation.py    # loads the .txt (no schema - free text, not structured)
├── presentation/
│   └── cli.py             # interactive chat loop: streams answers, prints sources + RAGAS scores, `python -m src.presentation.cli`
└── utils/
    ├── logging.py        # structured logging with per-turn correlation IDs
    └── token_counter.py  # approximate token counting (char-based heuristic)

tests/
├── unit/
│   ├── test_settings.py
│   ├── test_logging.py
│   ├── test_entities.py
│   ├── test_interfaces.py
│   ├── test_tavily_provider.py
│   ├── test_search_orchestrator.py
│   ├── test_deduplicator.py
│   ├── test_ranker.py
│   ├── test_token_counter.py
│   ├── test_content_extractor.py
│   ├── test_context_builder.py
│   ├── test_groq_client.py
│   ├── test_query_planner.py
│   ├── test_answer_generator.py
│   ├── test_pipeline.py          # full chain, real everywhere except SearchProvider/LLMProvider/Evaluator
│   ├── test_bootstrap.py
│   ├── test_ragas_evaluator.py
│   ├── test_evaluation_service.py
│   └── test_memory_cache.py
└── integration/
    ├── test_tavily_search.py     # real Tavily call, gated behind RUN_INTEGRATION_TESTS=1
    ├── test_query_planner.py     # real Groq call, gated behind RUN_INTEGRATION_TESTS=1
    ├── test_answer_generator.py    # incl. generate_streaming()/StreamedAnswer  # real Groq call, gated behind RUN_INTEGRATION_TESTS=1
    ├── test_ragas_evaluator.py   # real Groq call via RAGAS, gated behind RUN_INTEGRATION_TESTS=1
    └── test_pipeline.py          # full real end-to-end run (incl. evaluation), gated behind RUN_INTEGRATION_TESTS=1
```

## Setup

```bash
python -m venv venv
source venv/Scripts/activate    # Windows Git Bash; use venv\Scripts\activate.bat on cmd
pip install -e ".[dev]"
pip install --no-deps ragas==0.4.3
cp .env.example .env            # then fill in TAVILY_API_KEY and GROQ_API_KEY
```

`ragas` needs the extra `--no-deps` step because its normal install pulls
in `scikit-network` (a C-extension graph library with no Windows wheel,
needed only for a synthetic-testset-generation feature this project
doesn't use) - see [Decision 8.1](docs/decisions.md) for the full
investigation. Every other real dependency `ragas` needs is already
listed normally above.

## Running

```bash
python -m src.presentation.cli
```

Interactive terminal chat: ask a question, watch the answer stream in
token-by-token, then see its sources and RAGAS scores. Ctrl-C or Ctrl-D
(EOF) exits cleanly.
