"""Approximate token counting for context-budget enforcement.

Uses a plain character-count heuristic (~4 chars/token for English text)
rather than a real tokenizer. Two reasons: Groq serves Llama models, which
don't have a public tiktoken encoding anyway - tiktoken's cl100k_base would
itself only be an approximation here, not a ground truth. And tiktoken's
get_encoding() downloads its vocabulary file over the network on first use
(measured: ~15s cold, ~0.3s cached) - a hidden latency/network dependency
not worth taking on for what's already an approximation either way.
"""

_CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN) if text else 0


def truncate_to_token_count(text: str, max_tokens: int) -> str:
    """Truncate text to (approximately) max_tokens, by character count."""
    max_chars = max_tokens * _CHARS_PER_TOKEN
    return text[:max_chars]
