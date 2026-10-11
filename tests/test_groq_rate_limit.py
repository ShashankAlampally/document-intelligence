"""Exercise budget waits and SDK integration without network calls or real sleeps."""

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from groq import APIStatusError, Groq, RateLimitError

from app.config import Settings
from app.shared.groq_client import GroqModel
from app.shared.groq_rate_limit import GroqRateLimit, seconds


class FakeClock:
    def __init__(self):
        self.now = 0
        self.waits = []

    def time(self):
        return self.now

    def sleep(self, duration):
        self.waits.append(duration)
        self.now += duration


def handler(**settings):
    clock = FakeClock()
    limiter = GroqRateLimit(
        Settings(_env_file=None, **settings), clock=clock.time, sleeper=clock.sleep
    )
    return limiter, clock


def completion(tokens=10, headers=None):
    return SimpleNamespace(usage=SimpleNamespace(total_tokens=tokens)), headers or {}


def failure(status=429, headers=None):
    response = httpx.Response(
        status, headers=headers or {}, request=httpx.Request("POST", "https://api.groq.com")
    )
    error_type = RateLimitError if status == 429 else APIStatusError
    return error_type("simulated failure", response=response, body={})


def test_actual_usage_controls_next_call_and_expired_usage_is_removed(caplog):
    limiter, clock = handler(llm_tokens_per_minute=100)
    limiter.execute(lambda: completion(70), 90)
    limiter.execute(lambda: completion(20), 40)
    assert clock.waits == [60]
    assert list(limiter.usage) == [(60, 20)]
    assert "waiting 60.00s" in caplog.text


def test_small_actual_usage_releases_unused_output_reservation():
    limiter, clock = handler(llm_tokens_per_minute=100)
    limiter.execute(lambda: completion(10), 90)
    limiter.execute(lambda: completion(10), 90)
    assert clock.waits == []


def test_provider_remaining_budget_covers_usage_outside_this_process():
    limiter, clock = handler(llm_tokens_per_minute=100)
    limiter.execute(
        lambda: completion(
            10,
            {
                "x-ratelimit-limit-tokens": "100",
                "x-ratelimit-remaining-tokens": "5",
                "x-ratelimit-reset-tokens": "7.5s",
            },
        ),
        20,
    )
    limiter.execute(lambda: completion(), 20)
    assert clock.waits == [7.5]


@pytest.mark.parametrize(
    "headers, delay",
    [
        ({"retry-after": "4.5"}, 4.5),
        ({"retry-after-ms": "1500", "retry-after": "9"}, 1.5),
        ({}, 60),
    ],
)
def test_rate_limit_retries_same_call_after_provider_delay(headers, delay):
    limiter, clock = handler()
    request = Mock(side_effect=[failure(headers=headers), completion(25)])
    limiter.execute(request, 50)
    assert request.call_count == 2
    assert clock.waits == [delay]
    assert list(limiter.usage) == [(delay, 25)]


def test_exhausted_retries_preserve_rate_limit_exception():
    limiter, clock = handler(llm_rate_limit_retries=2)
    error = failure(headers={"retry-after": "2"})
    request = Mock(side_effect=error)
    with pytest.raises(RateLimitError) as caught:
        limiter.execute(request, 100)
    assert caught.value is error
    assert request.call_count == 3
    assert clock.waits == [2, 2]


def test_long_provider_wait_is_not_shortened_or_retried_early():
    limiter, clock = handler(llm_rate_limit_max_wait=30)
    request = Mock(side_effect=failure(headers={"retry-after": "3600"}))
    with pytest.raises(RateLimitError):
        limiter.execute(request, 100)
    assert request.call_count == 1
    assert clock.waits == []


def test_local_wait_limit_stops_before_another_request():
    limiter, clock = handler(llm_tokens_per_minute=100, llm_rate_limit_max_wait=10)
    limiter.execute(lambda: completion(90), 90)
    request = Mock()
    with pytest.raises(TimeoutError, match="token-budget wait"):
        limiter.execute(request, 90)
    request.assert_not_called()
    assert clock.waits == []


def test_authentication_error_is_not_retried():
    limiter, clock = handler()
    request = Mock(side_effect=failure(401))
    with pytest.raises(APIStatusError):
        limiter.execute(request, 100)
    assert request.call_count == 1
    assert clock.waits == []


def test_transient_server_failure_keeps_bounded_retry_support():
    limiter, clock = handler()
    request = Mock(side_effect=[failure(503), completion()])
    limiter.execute(request, 100)
    assert request.call_count == 2
    assert clock.waits == [1]


def test_estimate_includes_tool_schema_and_output_without_mutating_payload():
    limiter, _ = handler()
    arguments = {"messages": [{"role": "user", "content": "Hello"}], "max_completion_tokens": 100}
    estimate = limiter.estimate(arguments)
    assert limiter.estimate({**arguments, "tools": [{"schema": "x" * 400}]}) > estimate
    assert arguments["max_completion_tokens"] == 100


@pytest.mark.parametrize(
    "value, expected", [("2m3.5s", 123.5), ("200ms", 0.2), ("bad", 0), (None, 0)]
)
def test_provider_duration_formats(value, expected):
    assert seconds(value) == expected


def test_shared_client_uses_raw_headers_and_disables_sdk_retries(monkeypatch):
    limiter, clock = handler()
    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "2"},
                json={"error": {"message": "rate limit", "type": "rate_limit_error"}},
            )
        return httpx.Response(
            200,
            headers={"x-ratelimit-remaining-tokens": "100", "x-ratelimit-reset-tokens": "10s"},
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Done"},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    def create_client(**kwargs):
        assert kwargs["max_retries"] == 0
        return Groq(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))

    monkeypatch.setattr("groq.Groq", create_client)
    model = GroqModel(
        Settings(_env_file=None, groq_api_key="test-only", llm_max_tokens=100), rate_limit=limiter
    )
    try:
        result = model.complete([{"role": "user", "content": "Hello"}])
        assert result["message"]["content"] == "Done"
        assert len(requests) == 2
        assert clock.waits == [2]
        assert limiter.remaining == 100
        assert list(limiter.usage) == [(2, 15)]
    finally:
        model.client.close()
