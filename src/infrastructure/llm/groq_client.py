"""Groq adapter: the only place that knows Groq's SDK/response shape.

Implements both LLMProvider methods fully, even though only
generate_structured() is exercised until Phase 6 - an abc.ABC requires
every abstract method overridden before the class can be instantiated
at all, so there's no partial implementation to defer.
"""
from typing import TypeVar

from groq import AsyncGroq

from src.domain.interfaces import LLMProvider

T = TypeVar("T")


class GroqClient(LLMProvider):
    def __init__(self, api_key: str, fast_model: str, capable_model: str) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._fast_model = fast_model
        self._capable_model = capable_model

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        response = await self._client.chat.completions.create(
            model=self._capable_model,
            messages=self._build_messages(prompt, system_prompt),
        )
        return response.choices[0].message.content

    async def generate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T:
        response = await self._client.chat.completions.create(
            model=self._fast_model,
            messages=self._build_messages(prompt, system_prompt),
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return schema.model_validate_json(content)

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str | None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
