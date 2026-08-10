"""Groq adapter: the only place that knows Groq's SDK/response shape.

Implements both LLMProvider methods fully, even though only
generate_structured() is exercised until Phase 6 - an abc.ABC requires
every abstract method overridden before the class can be instantiated
at all, so there's no partial implementation to defer.

Retries only genuinely transient failures - APIConnectionError,
RateLimitError, InternalServerError - confirmed via Groq SDK source as
the retry-worthy subset of groq.APIStatusError. Non-transient failures
(bad request, auth, model not found) are not retried. Either way, every
failure that survives is re-raised as LLMGenerationError, so callers
never see a raw groq exception type.
"""
from typing import TypeVar

from groq import APIConnectionError, AsyncGroq, InternalServerError, RateLimitError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.domain.exceptions import LLMGenerationError
from src.domain.interfaces import LLMProvider

T = TypeVar("T")


class GroqClient(LLMProvider):
    def __init__(
        self,
        api_key: str,
        fast_model: str,
        capable_model: str,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._fast_model = fast_model
        self._capable_model = capable_model
        self._retrying = AsyncRetrying(
            stop=stop_after_attempt(max_retries),
            wait=wait_fixed(retry_backoff_seconds),
            retry=retry_if_exception_type(
                (APIConnectionError, RateLimitError, InternalServerError)
            ),
            reraise=True,
        )

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        try:
            response = await self._retrying(
                self._client.chat.completions.create,
                model=self._capable_model,
                messages=self._build_messages(prompt, system_prompt),
            )
        except Exception as exc:
            raise LLMGenerationError(f"Groq generate() failed: {exc}") from exc
        return response.choices[0].message.content

    async def generate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T:
        try:
            response = await self._retrying(
                self._client.chat.completions.create,
                model=self._fast_model,
                messages=self._build_messages(prompt, system_prompt),
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise LLMGenerationError(f"Groq generate_structured() failed: {exc}") from exc
        content = response.choices[0].message.content
        return schema.model_validate_json(content)

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str | None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
