import asyncio

import pytest

from src.infrastructure.cache.memory_cache import InMemoryCache


@pytest.mark.asyncio
async def test_get_on_missing_key_returns_none():
    cache = InMemoryCache()

    assert await cache.get("missing") is None


@pytest.mark.asyncio
async def test_set_then_get_returns_the_value():
    cache = InMemoryCache()

    await cache.set("key", "value", ttl_seconds=60)

    assert await cache.get("key") == "value"


@pytest.mark.asyncio
async def test_distinct_keys_do_not_collide():
    cache = InMemoryCache()

    await cache.set("a", "value-a", ttl_seconds=60)
    await cache.set("b", "value-b", ttl_seconds=60)

    assert await cache.get("a") == "value-a"
    assert await cache.get("b") == "value-b"


@pytest.mark.asyncio
async def test_setting_an_existing_key_overwrites_the_value():
    cache = InMemoryCache()

    await cache.set("key", "first", ttl_seconds=60)
    await cache.set("key", "second", ttl_seconds=60)

    assert await cache.get("key") == "second"


@pytest.mark.asyncio
async def test_entry_expires_after_its_ttl():
    cache = InMemoryCache()

    await cache.set("key", "value", ttl_seconds=0.05)
    assert await cache.get("key") == "value"

    await asyncio.sleep(0.1)

    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_arbitrary_value_types_are_stored_as_is():
    cache = InMemoryCache()
    value = {"nested": ["structure", 1, 2.0]}

    await cache.set("key", value, ttl_seconds=60)

    assert await cache.get("key") is value
