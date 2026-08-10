import httpx
import pytest
from groq import APIConnectionError, AuthenticationError, RateLimitError
from pydantic import BaseModel

from src.domain.exceptions import LLMGenerationError
from src.infrastructure.llm.groq_client import GroqClient


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.received_kwargs: dict | None = None

    async def create(self, **kwargs) -> _FakeResponse:
        self.received_kwargs = kwargs
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeGroqSDKClient:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)
        self.chat = _FakeChat(self.completions)


class DummySchema(BaseModel):
    value: str


def make_client(
    content: str, max_retries: int = 3, retry_backoff_seconds: float = 0
) -> tuple[GroqClient, _FakeGroqSDKClient]:
    client = GroqClient(
        api_key="test-key",
        fast_model="fast-model",
        capable_model="capable-model",
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    fake = _FakeGroqSDKClient(content)
    client._client = fake
    return client, fake


def _api_connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "https://api.groq.com"))


def _rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.groq.com")
    response = httpx.Response(status_code=429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def _authentication_error() -> AuthenticationError:
    request = httpx.Request("POST", "https://api.groq.com")
    response = httpx.Response(status_code=401, request=request)
    return AuthenticationError("bad key", response=response, body=None)


class _FlakyThenOkCompletions:
    """Fails with a retryable error `fail_times` times, then succeeds."""

    def __init__(self, content: str, exc: Exception, fail_times: int) -> None:
        self._content = content
        self._exc = exc
        self._fail_times = fail_times
        self.call_count = 0

    async def create(self, **kwargs) -> _FakeResponse:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise self._exc
        return _FakeResponse(self._content)


class _AlwaysFailsCompletions:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.call_count = 0

    async def create(self, **kwargs) -> _FakeResponse:
        self.call_count += 1
        raise self._exc


@pytest.mark.asyncio
async def test_generate_returns_plain_text_using_capable_model():
    client, fake = make_client("hello world")

    result = await client.generate("prompt")

    assert result == "hello world"
    assert fake.completions.received_kwargs["model"] == "capable-model"


@pytest.mark.asyncio
async def test_generate_structured_parses_and_validates_using_fast_model():
    client, fake = make_client('{"value": "abc"}')

    result = await client.generate_structured("prompt", schema=DummySchema)

    assert result == DummySchema(value="abc")
    assert fake.completions.received_kwargs["model"] == "fast-model"
    assert fake.completions.received_kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_generate_structured_raises_on_invalid_json():
    client, _ = make_client("not valid json")

    with pytest.raises(Exception):
        await client.generate_structured("prompt", schema=DummySchema)


@pytest.mark.asyncio
async def test_system_prompt_included_as_first_message_when_provided():
    client, fake = make_client("hi")

    await client.generate("prompt", system_prompt="be nice")

    messages = fake.completions.received_kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "be nice"}
    assert messages[1] == {"role": "user", "content": "prompt"}


@pytest.mark.asyncio
async def test_no_system_message_when_not_provided():
    client, fake = make_client("hi")

    await client.generate("prompt")

    messages = fake.completions.received_kwargs["messages"]
    assert messages == [{"role": "user", "content": "prompt"}]


@pytest.mark.asyncio
async def test_generate_retries_transient_errors_and_eventually_succeeds():
    client, fake = make_client("hello world")
    fake.chat.completions = _FlakyThenOkCompletions(
        "hello world", _api_connection_error(), fail_times=2
    )

    result = await client.generate("prompt")

    assert result == "hello world"
    assert fake.chat.completions.call_count == 3


@pytest.mark.asyncio
async def test_generate_raises_llm_generation_error_after_exhausting_retries():
    client, fake = make_client("hello world", max_retries=2)
    fake.chat.completions = _AlwaysFailsCompletions(_rate_limit_error())

    with pytest.raises(LLMGenerationError):
        await client.generate("prompt")

    assert fake.chat.completions.call_count == 2


@pytest.mark.asyncio
async def test_generate_does_not_retry_non_transient_errors():
    client, fake = make_client("hello world", max_retries=3)
    fake.chat.completions = _AlwaysFailsCompletions(_authentication_error())

    with pytest.raises(LLMGenerationError):
        await client.generate("prompt")

    assert fake.chat.completions.call_count == 1


@pytest.mark.asyncio
async def test_generate_structured_raises_llm_generation_error_on_transient_failure():
    client, fake = make_client('{"value": "abc"}', max_retries=2)
    fake.chat.completions = _AlwaysFailsCompletions(_api_connection_error())

    with pytest.raises(LLMGenerationError):
        await client.generate_structured("prompt", schema=DummySchema)

    assert fake.chat.completions.call_count == 2
