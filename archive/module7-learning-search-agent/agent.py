"""
Builds the search agent itself.

This is the LLM -> Reasoning -> Search Tool -> Retrieve part of the
Module 7 architecture. create_agent (Module 2) builds a ReAct-style
loop on top of LangGraph for us: the model reasons, calls the search
tool when it needs to, reads the results, and repeats until it has
enough to answer.
"""
from datetime import datetime

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from config import Config
from tools import get_search_tool

# Injecting today's date is a direct, cheap accuracy win (Module 3) --
# without it the model can misjudge what counts as "recent."
SYSTEM_PROMPT_TEMPLATE = """You are a careful research assistant. Today's date is {today}.

Rules:
1. Search before answering any question that is factual, time-sensitive,
   or something you are not fully certain about. Do not answer purely
   from memory if it could be wrong or outdated.
2. Base your answer only on what the search results actually say.
   Do not add claims the sources don't support.
3. Be concise. No filler, no unnecessary hedging.
4. If the search results don't clearly answer the question, say so
   honestly instead of guessing.
"""


def build_agent():
    """Construct and return the search agent. Raises EnvironmentError early
    if required API keys are missing (see Config.validate)."""
    Config.validate()

    search_tool = get_search_tool()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        today=datetime.today().strftime("%B %d, %Y")
    )

    model = ChatGoogleGenerativeAI(
        model=Config.MODEL_NAME,
        google_api_key=Config.GOOGLE_API_KEY,
    )

    return create_agent(
        model=model,           # an instance now, not a "provider:model" string
        tools=[search_tool],
        system_prompt=system_prompt,
    )
