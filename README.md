# AI Search Chatbot

An interactive research chatbot: dynamic query planning → parallel Tavily
search → dedup/rank → grounded Groq answer → RAGAS evaluation.

Full architecture, design decisions, and the phased roadmap live in
[`docs/`](docs/) — see [`docs/architecture.md`](docs/architecture.md),
[`docs/decisions.md`](docs/decisions.md), and
[`docs/roadmap.md`](docs/roadmap.md). Build notes for each completed phase
are in [`docs/phases/`](docs/phases/).

An earlier learning prototype (LangChain `create_agent` + Tavily + Gemini)
is preserved as-is in
[`archive/module7-learning-search-agent/`](archive/module7-learning-search-agent/)
for reference; it is not part of the active codebase.

## Architecture

Clean architecture, inner layers depending on nothing outward:

- **`src/domain/`** — entities (`Query`, `SearchResult`, `Source`, `Answer`, `EvaluationResult`) and interfaces (`SearchProvider`, `LLMProvider`, `Ranker`, `Evaluator`, `Cache`). No I/O, no external libraries.
- **`src/application/`** — orchestration logic that depends only on the interfaces above. `SearchOrchestrator` implemented; the rest is not yet.
- **`src/infrastructure/`** — concrete adapters (Tavily, Groq, RAGAS, cache) implementing those interfaces. `TavilyProvider` implemented; the rest is not yet.
- **`src/presentation/`** — CLI entry point. Not yet implemented.

Full pipeline diagram and component responsibilities: [`docs/architecture.md`](docs/architecture.md).

## Current Progress

- [x] Phase 0 — Project scaffolding
- [x] Phase 1 — Domain layer
- [x] Phase 2 — Search integration
- [ ] Phase 3 — Dedup + ranking
- [ ] Phase 4 — Context building
- [ ] Phase 5 — Query planning
- [ ] Phase 6 — Answer generation
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
│   └── interfaces.py     # SearchProvider, LLMProvider, Ranker, Evaluator, Cache
├── application/
│   └── search_orchestrator.py  # concurrent fan-out over a SearchProvider, per-query timeout
├── infrastructure/
│   ├── search/
│   │   └── tavily_provider.py  # implements SearchProvider via Tavily's async client
│   ├── llm/                (empty)
│   ├── evaluation/        (empty)
│   ├── cache/              (empty)
│   └── content/           (empty)
├── config/
│   ├── settings.py       # pydantic-settings, validated env config
│   └── prompts/            (empty)
├── presentation/          (empty)
└── utils/
    └── logging.py        # structured logging with per-turn correlation IDs

tests/
├── unit/
│   ├── test_settings.py
│   ├── test_logging.py
│   ├── test_entities.py
│   ├── test_interfaces.py
│   ├── test_tavily_provider.py
│   └── test_search_orchestrator.py
└── integration/
    └── test_tavily_search.py   # real Tavily call, gated behind RUN_INTEGRATION_TESTS=1
```

## Setup

```bash
python -m venv venv
source venv/Scripts/activate    # Windows Git Bash; use venv\Scripts\activate.bat on cmd
pip install -e ".[dev]"
cp .env.example .env            # then fill in TAVILY_API_KEY and GROQ_API_KEY
```
