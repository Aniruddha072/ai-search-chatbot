"""System prompt for answer generation.

Like query_planning.py, the prompt text lives in a .txt file, not here
(Decision 5.5's pattern, continued). No response schema in this module -
unlike query planning, this is free-text generation (LLMProvider.generate,
not generate_structured), since AnswerGenerator needs to parse citation
markers out of prose, not validate a fixed JSON shape.
"""
from pathlib import Path

SYSTEM_PROMPT = (Path(__file__).parent / "answer_generation.txt").read_text(encoding="utf-8")
