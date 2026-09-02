import pytest
from muxivo_console.infrastructure.rate_limiting import (
    InMemoryFixedWindowRateLimiter,
    RateLimitRule,
    RedisFixedWindowRateLimiter,
    RedisRateLimitUnavailableError,
)


@pytest.mark.asyncio
async def test_fixed_window_limiter_denies_after_scope_limit() -> None:
    limiter = InMemoryFixedWindowRateLimiter({"auth.login": RateLimitRule(2, 60)})

    first = await limiter.check(scope="auth.login", key="client-a")
    second = await limiter.check(scope="auth.login", key="client-a")
    third = await limiter.check(scope="auth.login", key="client-a")

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after_seconds >= 1


@pytest.mark.asyncio
async def test_fixed_window_limiter_is_scoped_by_client_key() -> None:
    limiter = InMemoryFixedWindowRateLimiter({"auth.login": RateLimitRule(1, 60)})

    await limiter.check(scope="auth.login", key="client-a")
    second_client = await limiter.check(scope="auth.login", key="client-b")

    assert second_client.allowed is True


@pytest.mark.asyncio
async def test_missing_rate_limit_rule_fails_open_for_unprotected_scope() -> None:
    limiter = InMemoryFixedWindowRateLimiter({})

    decision = await limiter.check(scope="unprotected", key="client-a")

    assert decision.allowed is True


class FakeRedisCounter:
    def __init__(self, responses: list[tuple[int, int]] | None = None, unavailable: bool = False):
        self.responses = responses or [(1, 60)]
        self.unavailable = unavailable
        self.calls: list[tuple[str, int]] = []

    async def increment_windowed(self, *, key: str, window_seconds: int) -> tuple[int, int]:
        self.calls.append((key, window_seconds))
        if self.unavailable:
            raise RedisRateLimitUnavailableError("Redis unavailable.")
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_redis_limiter_uses_shared_counter_and_hashes_client_key() -> None:
    counter = FakeRedisCounter([(1, 60)])
    limiter = RedisFixedWindowRateLimiter(
        rules={"auth.login": RateLimitRule(2, 60)},
        counter=counter,
    )

    decision = await limiter.check(scope="auth.login", key="203.0.113.10")

    assert decision.allowed is True
    assert counter.calls[0][1] == 60
    assert "203.0.113.10" not in counter.calls[0][0]
    assert counter.calls[0][0].startswith("muxivo-console:rate-limit:auth.login:")


@pytest.mark.asyncio
async def test_redis_limiter_denies_after_shared_limit() -> None:
    counter = FakeRedisCounter([(3, 42)])
    limiter = RedisFixedWindowRateLimiter(
        rules={"auth.login": RateLimitRule(2, 60)},
        counter=counter,
    )

    decision = await limiter.check(scope="auth.login", key="client-a")

    assert decision.allowed is False
    assert decision.retry_after_seconds == 42


@pytest.mark.asyncio
async def test_redis_limiter_fails_closed_when_backend_is_unavailable() -> None:
    limiter = RedisFixedWindowRateLimiter(
        rules={"auth.login": RateLimitRule(2, 60)},
        counter=FakeRedisCounter(unavailable=True),
    )

    decision = await limiter.check(scope="auth.login", key="client-a")

    assert decision.allowed is False
    assert decision.retry_after_seconds == 60
