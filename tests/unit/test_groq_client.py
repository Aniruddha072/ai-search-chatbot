import pytest
from pydantic import BaseModel

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


def make_client(content: str) -> tuple[GroqClient, _FakeGroqSDKClient]:
    client = GroqClient(api_key="test-key", fast_model="fast-model", capable_model="capable-model")
    fake = _FakeGroqSDKClient(content)
    client._client = fake
    return client, fake


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
