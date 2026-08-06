# AI Search Chatbot

An interactive research chatbot: dynamic query planning → parallel Tavily
search → dedup/rank → grounded Groq answer → RAGAS evaluation.

Full architecture, diagrams, and the phased roadmap live in
[`docs/ai-search-chatbot-architecture.md`](docs/ai-search-chatbot-architecture.md).
Build history and per-phase notes are in [`DEVLOG.md`](DEVLOG.md).

An earlier learning prototype (LangChain `create_agent` + Tavily + Gemini)
is preserved as-is in
[`archive/module7-learning-search-agent/`](archive/module7-learning-search-agent/)
for reference; it is not part of the active codebase.

**Status:** Phase 0 (project scaffolding) — implementation in progress.

## Setup

```bash
python -m venv venv
source venv/Scripts/activate    # Windows Git Bash; use venv\Scripts\activate.bat on cmd
pip install -e ".[dev]"
cp .env.example .env            # then fill in TAVILY_API_KEY and GROQ_API_KEY
```
