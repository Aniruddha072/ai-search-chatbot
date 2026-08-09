import asyncio

import pytest

from src.application.answer_generator import AnswerGenerator
from src.domain.entities import Query, Source
from src.domain.interfaces import LLMProvider


def make_query(text: str = "best CE colleges in Pune") -> Query:
    return Query(original_text=text, sub_queries=(text,), intent="find colleges", complexity="simple")


def make_sources(*titles: str) -> tuple[Source, ...]:
    return tuple(
        Source(index=i + 1, url=f"https://example.com/{i}", title=title, content_used=f"Content for {title}")
        for i, title in enumerate(titles)
    )


class FakeLLMProvider(LLMProvider):
    def __init__(self, response_text: str | None = None, raise_exc: Exception | None = None, delay: float = 0.0):
        self._response_text = response_text
        self._raise_exc = raise_exc
        self._delay = delay
        self.received_prompt: str | None = None
        self.received_system_prompt: str | None = None

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        self.received_prompt = prompt
        self.received_system_prompt = system_prompt
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raise_exc:
            raise self._raise_exc
        return self._response_text

    async def generate_structured(self, prompt, schema, *, system_prompt=None):
        raise NotImplementedError("AnswerGenerator should never call generate_structured")


@pytest.mark.asyncio
async def test_prompt_includes_all_sources_and_the_question():
    sources = make_sources("PCCOE", "COEP")
    provider = FakeLLMProvider(response_text="answer [1][2]")
    generator = AnswerGenerator(provider, timeout_seconds=5.0)

    await generator.generate(make_query("best CE colleges in Pune"), sources)

    assert "[1] Title: PCCOE" in provider.received_prompt
    assert "[2] Title: COEP" in provider.received_prompt
    assert "Content for PCCOE" in provider.received_prompt
    assert "best CE colleges in Pune" in provider.received_prompt


@pytest.mark.asyncio
async def test_citations_are_mapped_to_correct_sources():
    sources = make_sources("PCCOE", "COEP", "Weather")
    provider = FakeLLMProvider(response_text="PCCOE is great [1]. COEP is also good [2].")
    generator = AnswerGenerator(provider, timeout_seconds=5.0)

    answer = await generator.generate(make_query(), sources)

    assert [s.title for s in answer.sources] == ["PCCOE", "COEP"]


@pytest.mark.asyncio
async def test_duplicate_citations_are_deduplicated():
    sources = make_sources("PCCOE")
    provider = FakeLLMProvider(response_text="PCCOE is great [1]. Really, [1] is the best [1].")
    generator = AnswerGenerator(provider, timeout_seconds=5.0)

    answer = await generator.generate(make_query(), sources)

    assert len(answer.sources) == 1
    assert answer.sources[0].title == "PCCOE"


@pytest.mark.asyncio
async def test_out_of_range_citation_is_ignored():
    sources = make_sources("PCCOE")
    provider = FakeLLMProvider(response_text="PCCOE is great [1]. Also see [99].")
    generator = AnswerGenerator(provider, timeout_seconds=5.0)

    answer = await generator.generate(make_query(), sources)

    assert len(answer.sources) == 1
    assert answer.sources[0].title == "PCCOE"


@pytest.mark.asyncio
async def test_no_citations_returns_empty_sources_tuple():
    sources = make_sources("PCCOE")
    provider = FakeLLMProvider(response_text="The sources do not contain enough information.")
    generator = AnswerGenerator(provider, timeout_seconds=5.0)

    answer = await generator.generate(make_query(), sources)

    assert answer.sources == ()
    assert answer.text == "The sources do not contain enough information."


@pytest.mark.asyncio
async def test_llm_exception_propagates():
    provider = FakeLLMProvider(raise_exc=RuntimeError("boom"))
    generator = AnswerGenerator(provider, timeout_seconds=5.0)

    with pytest.raises(RuntimeError):
        await generator.generate(make_query(), make_sources("PCCOE"))


@pytest.mark.asyncio
async def test_timeout_propagates():
    provider = FakeLLMProvider(response_text="too slow", delay=1.0)
    generator = AnswerGenerator(provider, timeout_seconds=0.05)

    with pytest.raises(asyncio.TimeoutError):
        await generator.generate(make_query(), make_sources("PCCOE"))
