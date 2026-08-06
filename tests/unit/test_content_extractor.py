import pytest

from src.infrastructure.content import content_extractor as content_extractor_module
from src.infrastructure.content.content_extractor import TrafilaturaContentExtractor


@pytest.mark.asyncio
async def test_extract_returns_cleaned_text_on_success(monkeypatch):
    monkeypatch.setattr(
        content_extractor_module.trafilatura, "fetch_url", lambda url: "<html>raw</html>"
    )
    monkeypatch.setattr(
        content_extractor_module.trafilatura, "extract", lambda html: "clean extracted text"
    )

    result = await TrafilaturaContentExtractor().extract("https://example.com")

    assert result == "clean extracted text"


@pytest.mark.asyncio
async def test_extract_returns_none_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(content_extractor_module.trafilatura, "fetch_url", lambda url: None)

    result = await TrafilaturaContentExtractor().extract("https://example.com/404")

    assert result is None


@pytest.mark.asyncio
async def test_extract_returns_none_when_extraction_finds_nothing(monkeypatch):
    monkeypatch.setattr(
        content_extractor_module.trafilatura, "fetch_url", lambda url: "<html></html>"
    )
    monkeypatch.setattr(content_extractor_module.trafilatura, "extract", lambda html: None)

    result = await TrafilaturaContentExtractor().extract("https://example.com/empty")

    assert result is None
