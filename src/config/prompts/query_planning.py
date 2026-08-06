"""Prompt and response schema for query planning.

The prompt text lives in query_planner.txt, not here, so it can be edited
without touching Python. It's a hand-written natural-language description
plus one worked example - not a raw JSON Schema dump. That distinction
matters: a raw schema (with "title"/"type"/"$defs" metadata) confused
llama-3.1-8b-instant into echoing schema fragments instead of producing
actual data, verified empirically before writing this.
"""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SYSTEM_PROMPT = (Path(__file__).parent / "query_planner.txt").read_text(encoding="utf-8")


class QueryPlanResponse(BaseModel):
    intent: str
    complexity: Literal["simple", "moderate", "complex"]
    queries: list[str] = Field(min_length=1, max_length=5)
