"""
Configuration for the search agent.

Everything that reads an environment variable or holds a project-wide
setting lives here, so no other file in the project touches os.environ
directly. If a setting needs to change, this is the one file to open.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Plain model name -- no provider prefix needed here, since agent.py
    # and evaluator.py now construct ChatGoogleGenerativeAI directly
    # instead of going through init_chat_model's "provider:model" parsing.
    MODEL_NAME = os.getenv("MODEL_NAME", "gemini-flash-latest")

    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))

    # "advanced" by default: your project's mandate ranks accuracy above
    # cost/latency (see Module 3). Override in .env if you want to test
    # "basic" or "fast" instead.
    SEARCH_DEPTH = os.getenv("SEARCH_DEPTH", "advanced")

    @classmethod
    def validate(cls) -> None:
        """Fail loudly and early if required keys are missing, instead of
        letting the agent fail confusingly three calls deep."""
        missing = [
            name
            for name, value in [
                ("GOOGLE_API_KEY", cls.GOOGLE_API_KEY),
                ("TAVILY_API_KEY", cls.TAVILY_API_KEY),
            ]
            if not value
        ]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in."
            )
