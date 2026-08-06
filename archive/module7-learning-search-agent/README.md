# Search Agent — v1 (simplest working build)

A minimal, real, working AI search agent: LangChain's `create_agent` +
Tavily search + a lightweight faithfulness check. Built to be
understood end-to-end in one sitting, not to be a framework.

## Architecture

```
 User question
      │
      ▼
 ┌─────────────────────────────────────────┐
 │  create_agent  (agent.py)                 │
 │                                            │
 │   LLM reasons ──▶ calls search tool         │
 │        ▲                  │                 │
 │        └── observes results ┘               │
 │   (repeats until it has enough to answer)   │
 └─────────────────────┬─────────────────────┘
                        │  answer + raw search results
                        ▼
 ┌─────────────────────────────────────────┐
 │  evaluate_faithfulness  (evaluator.py)     │
 │  fresh LLM call: is every claim in the    │
 │  answer actually supported by the sources? │
 └─────────────────────┬─────────────────────┘
                        │
                        ▼
                 Final answer (+ warning
                 if unsupported claims found)
```

This maps directly onto the curriculum's target architecture
(User → LLM → Reasoning → Search Tool → Retrieve → Evaluate →
Summarize → Answer). `create_agent` collapses the middle four steps
into one loop; `evaluator.py` is the Evaluate step; the final printed
string is Summarize/Answer.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your real API keys
python main.py
```

Get a Google API key at aistudio.google.com/apikey (Gemini's free tier
is generous enough for this kind of testing) and a Tavily key at
app.tavily.com (free tier: 1,000 credits/month, no card required —
see Module 3).

## Files, and what each function does

**`config.py`** — every environment variable and setting, in one place.
- `Config` — a plain class holding settings (model name, search depth,
  max results, API keys read from `.env`).
- `Config.validate()` — checks the required keys are present and raises
  a clear error immediately if not, instead of letting the agent fail
  confusingly on its first tool call.

**`tools.py`** — the agent's tools. Just one for v1.
- `get_search_tool()` — builds a `TavilySearch` instance using the
  project's standard settings from `Config`. Adding a second tool later
  (e.g. an Apify scraper for a specific known site) means adding one
  function here, no changes anywhere else.

**`agent.py`** — builds the actual agent.
- `build_agent()` — validates config, builds the search tool, formats
  the system prompt with today's date (a direct accuracy lever from
  Module 3 — without it the model can misjudge what "recent" means),
  and returns a `create_agent` instance. This one call is doing
  everything Module 1's manual ReAct loop did by hand, and everything
  Module 2's raw `create_agent` example did — just wired to a real
  search tool now.

**`evaluator.py`** — the faithfulness check (Module 6, in its simplest
working form).
- `FaithfulnessCheck` — a Pydantic model defining the structured
  verdict: is the answer faithful, which claims (if any) aren't
  supported, and a one-line explanation.
- `evaluate_faithfulness(question, answer, sources_text)` — makes a
  *separate* LLM call (deliberately not reusing the agent's own
  conversation, to avoid a model rubber-stamping its own work) asking
  it to check the answer against the raw search results only. Returns
  early with a clear "no sources" verdict if nothing was retrieved,
  rather than asking a model to judge against nothing.

**`main.py`** — entry point, ties everything together.
- `extract_sources_text(agent_result)` — pulls the raw tool-call
  results out of the agent's message history (identified by
  `msg.type == "tool"`) so the evaluator has real source text to check
  against.
- `ask(agent, question, verify=True)` — runs one question through the
  agent, then (if `verify=True`) runs the faithfulness check and
  appends a warning if it flags anything. This is the full pipeline in
  one function.
- `main()` — a simple command-line loop: build the agent once, then
  read questions until the user types `exit`.

## What's deliberately NOT in this v1

This was scoped as "simplest working version first," so the following
are real, known gaps — not oversights:

- **No conversation memory across turns.** Each question is a fresh
  `agent.invoke()` call with no `checkpointer` (Module 2). Fine for a
  single-question CLI; a next step for anything conversational.
- **No proper evaluation harness.** `evaluator.py` is one faithfulness
  check per answer, not the golden-dataset + RAGAS-metrics setup from
  Module 6. Good enough to catch obvious hallucination in real time;
  not good enough to benchmark search_depth or compare search APIs —
  that needs the real harness from Module 6's exercise.
- **One tool, one search provider.** No fallback if Tavily is down, no
  second search API for comparison, no Apify integration for
  known-site extraction.
- **No retries or rate-limit handling** on the API calls themselves.
- **Synchronous, single-user CLI.** No async, no API server, no
  concurrent requests.

## Natural next optimizations (for later, on purpose)

- Add a `checkpointer` for multi-turn memory (Module 2).
- Swap the single faithfulness check for the full RAGAS-style harness
  from Module 6, run against a golden dataset, so `SEARCH_DEPTH` and
  tool choice become evidence-based decisions instead of defaults.
- Add a second search tool (Exa, for semantic/discovery queries) or an
  Apify tool (for a specific known site) and let the agent choose —
  this is where good tool docstrings (Module 2) start to really matter.
- Wrap `ask()` in a small FastAPI app instead of a CLI loop, once this
  needs to serve more than one user.
