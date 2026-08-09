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
- **`src/application/`** — orchestration logic that depends only on the interfaces above. `SearchOrchestrator`, `Deduplicator`, `HeuristicRanker`, `ContextBuilder`, `QueryPlanner`, `AnswerGenerator` implemented; the rest is not yet.
- **`src/infrastructure/`** — concrete adapters (Tavily, Groq, RAGAS, cache) implementing those interfaces. `TavilyProvider`, `TrafilaturaContentExtractor`, `GroqClient` implemented; the rest is not yet.
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
- [ ] Phase 7 — Pipeline wiring
- [ ] Phase 8 — RAGAS evaluation
- [ ] Phase 9 — Caching
- [ ] Phase 10 — Resilience hardening
- [ ] Phase 11 — CLI presentation
- [ ] Phase 12 — Testing
- [ ] Phase 13 — Observability & polish
- [ ] Phase 14 — Optional: FastAPI layer

## Project Structure

```
src/
├── domain/
│   ├── entities.py       # Query, SearchResult, Source, Answer, EvaluationResult
│   └── interfaces.py     # SearchProvider, LLMProvider, Ranker, Evaluator, ContentExtractor, Cache
├── application/
│   ├── search_orchestrator.py  # concurrent fan-out over a SearchProvider, per-query timeout
│   ├── deduplicator.py         # URL normalization + near-duplicate content passes
│   ├── ranker.py               # HeuristicRanker: weighted provider/keyword/recency scoring
│   ├── context_builder.py      # top-K selection, thin-snippet full-fetch, token-budget enforcement
│   ├── query_planner.py        # Groq structured-output call -> Query, with single-query fallback
│   └── answer_generator.py     # Groq generate() -> cited Answer; failures propagate, no fallback
├── infrastructure/
│   ├── search/
│   │   └── tavily_provider.py  # implements SearchProvider via Tavily's async client
│   ├── llm/
│   │   └── groq_client.py      # implements LLMProvider (generate + generate_structured)
│   ├── evaluation/        (empty)
│   ├── cache/              (empty)
│   └── content/
│       └── content_extractor.py  # TrafilaturaContentExtractor implements ContentExtractor
├── config/
│   ├── settings.py       # pydantic-settings, validated env config
│   └── prompts/
│       ├── query_planner.txt       # system prompt text, plain text, not Python
│       ├── query_planning.py       # loads the .txt + QueryPlanResponse schema
│       ├── answer_generation.txt   # cite-or-refuse system prompt, plain text
│       └── answer_generation.py    # loads the .txt (no schema - free text, not structured)
├── presentation/          (empty)
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
│   └── test_answer_generator.py
└── integration/
    ├── test_tavily_search.py     # real Tavily call, gated behind RUN_INTEGRATION_TESTS=1
    ├── test_query_planner.py     # real Groq call, gated behind RUN_INTEGRATION_TESTS=1
    └── test_answer_generator.py  # real Groq call, gated behind RUN_INTEGRATION_TESTS=1
```

## Setup

```bash
python -m venv venv
source venv/Scripts/activate    # Windows Git Bash; use venv\Scripts\activate.bat on cmd
pip install -e ".[dev]"
cp .env.example .env            # then fill in TAVILY_API_KEY and GROQ_API_KEY
```
