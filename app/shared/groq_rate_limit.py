"""Pace shared model calls and retry provider failures without changing agents."""

import json
import logging
import math
import re
from collections import deque
from email.utils import parsedate_to_datetime
from threading import Lock
from time import monotonic, sleep, time

logger = logging.getLogger(__name__)


def seconds(value: str | None) -> float:
    """Read Groq reset durations such as '2m3.5s'; unknown values mean zero."""
    if not value:
        return 0
    try:
        return max(0, float(value))
    except ValueError:
        parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value)
        if "".join(number + unit for number, unit in parts) != value:
            return 0
        factors = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
        return sum(float(number) * factors[unit] for number, unit in parts)


class GroqRateLimit:
    def __init__(self, settings, *, clock=monotonic, sleeper=sleep, event_sink=None):
        self.event_sink = event_sink
        self.limit = settings.llm_tokens_per_minute
        self.retries = settings.llm_rate_limit_retries
        self.max_wait = settings.llm_rate_limit_max_wait
        self.clock = clock
        self.sleep = sleeper
        self.lock = Lock()
        self.usage = deque()
        self.remaining = None
        self.reset_at = 0
        self.cooldown_until = 0

    def _emit(self, stage, **details):
        if self.event_sink is not None:
            self.event_sink({"stage": stage, **details})

    def estimate(self, arguments: dict) -> int:
        # Includes messages, tool/schema definitions and room for the output.
        # This is a heuristic, not the model tokenizer; never truncate evidence.
        prompt = {key: value for key, value in arguments.items() if key != "max_completion_tokens"}
        return math.ceil(len(json.dumps(prompt, ensure_ascii=False)) / 4) + arguments.get(
            "max_completion_tokens", 0
        )

    def execute(self, request, estimated_tokens: int):
        """request returns (parsed completion, response headers). Serialize callers."""
        with self.lock:
            deadline = self.clock() + self.max_wait
            # An approximate oversized estimate must not reject a valid request.
            budget = min(estimated_tokens, self.limit)
            for attempt in range(self.retries + 1):
                self._wait_for_budget(budget, deadline)
                started = self.clock()
                self._emit(
                    "groq_request_start",
                    attempt=attempt + 1,
                    estimated_tokens=estimated_tokens,
                    budget_tokens=budget,
                )
                try:
                    response, headers = request()
                except Exception as error:
                    status = getattr(error, "status_code", None)
                    retryable = (
                        status in (408, 409, 429)
                        or (isinstance(status, int) and status >= 500)
                        or type(error).__name__ in ("APIConnectionError", "APITimeoutError")
                    )
                    self._emit(
                        "groq_request_error",
                        attempt=attempt + 1,
                        status_code=status,
                        error=type(error).__name__,
                        error_detail=str(error),
                        retryable=retryable,
                        elapsed_seconds=self.clock() - started,
                    )
                    if not retryable:
                        raise
                    headers = getattr(getattr(error, "response", None), "headers", {})
                    self._update_headers(headers)
                    delay = self._retry_delay(headers, status, attempt)
                    self.cooldown_until = max(self.cooldown_until, self.clock() + delay)
                    # Preserve the original exception so the API can return HTTP 429.
                    if attempt == self.retries or self.cooldown_until > deadline:
                        self._emit(
                            "groq_retry_stopped",
                            attempt=attempt + 1,
                            reason="retry_limit" if attempt == self.retries else "wait_limit",
                            delay_seconds=delay,
                        )
                        raise
                    self._emit(
                        "groq_retry",
                        next_attempt=attempt + 2,
                        status_code=status,
                        delay_seconds=delay,
                    )
                    logger.warning(
                        "Groq status=%s; retry %s/%s in %.2fs",
                        status,
                        attempt + 1,
                        self.retries,
                        delay,
                    )
                    continue
                usage = getattr(response, "usage", None)
                actual = getattr(usage, "total_tokens", None)
                tokens = actual if isinstance(actual, int) else estimated_tokens
                self.usage.append((self.clock(), tokens))
                self._update_headers(headers)
                self._emit(
                    "groq_request_end",
                    attempt=attempt + 1,
                    elapsed_seconds=self.clock() - started,
                    total_tokens=tokens,
                    remaining_tokens=self.remaining,
                    tokens_per_minute=self.limit,
                )
                return response

    def _wait_for_budget(self, tokens: int, deadline: float) -> None:
        while True:
            now = self.clock()
            while self.usage and self.usage[0][0] + 60 <= now:
                self.usage.popleft()
            if now >= self.reset_at:
                self.remaining = None
            wait = max(0, self.cooldown_until - now)
            used = sum(count for _, count in self.usage)
            if self.usage and used + tokens > self.limit:
                wait = max(wait, self.usage[0][0] + 60 - now)
            if self.remaining is not None and tokens > self.remaining:
                wait = max(wait, self.reset_at - now)
            if wait <= 0:
                return
            if now + wait > deadline:
                self._emit("groq_wait_stopped", wait_seconds=wait, reason="wait_limit")
                raise TimeoutError("Groq token-budget wait exceeded configured maximum")
            logger.warning("Groq budget: waiting %.2fs before model call", wait)
            self._emit(
                "groq_wait_start",
                wait_seconds=wait,
                used_tokens=used,
                remaining_tokens=self.remaining,
                tokens_per_minute=self.limit,
                cooldown_seconds=max(0, self.cooldown_until - now),
            )
            started = self.clock()
            try:
                self.sleep(wait)
            except BaseException:
                self._emit(
                    "groq_wait_end", elapsed_seconds=self.clock() - started, interrupted=True
                )
                raise
            self._emit("groq_wait_end", elapsed_seconds=self.clock() - started, interrupted=False)

    def _update_headers(self, headers) -> None:
        try:
            limit = int(headers.get("x-ratelimit-limit-tokens", self.limit))
            if limit > 0:
                self.limit = limit
            remaining = int(headers["x-ratelimit-remaining-tokens"])
            reset = seconds(headers.get("x-ratelimit-reset-tokens"))
            if reset > 0:
                self.remaining = max(0, remaining)
                self.reset_at = self.clock() + reset
        except (KeyError, TypeError, ValueError):
            pass

    def _retry_delay(self, headers, status, attempt: int) -> float:
        value = headers.get("retry-after-ms")
        if value is not None:
            try:
                return max(0, float(value) / 1000)
            except ValueError:
                pass
        value = headers.get("retry-after")
        if value is not None:
            try:
                return max(0, float(value))
            except ValueError:
                try:
                    return max(0, parsedate_to_datetime(value).timestamp() - time())
                except (TypeError, ValueError, OverflowError):
                    pass
        if status == 429:
            return max(60, seconds(headers.get("x-ratelimit-reset-tokens")))
        return min(2**attempt, 8)
