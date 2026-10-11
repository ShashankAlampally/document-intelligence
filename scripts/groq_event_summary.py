"""Summarize saved events from this run, including interrupted calls."""

import json
from collections import Counter


def summarize_events(directory):
    path = directory / "events.jsonl"
    if not path.exists():
        return {}
    counts = Counter()
    statuses = Counter()
    waits = 0.0
    tokens = 0
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            counts["incomplete_event_lines"] += 1
            continue
        counts[event["stage"]] += 1
        if event["stage"] == "groq_wait_end":
            waits += event.get("elapsed_seconds", 0)
        if event["stage"] == "groq_request_error":
            statuses[str(event.get("status_code"))] += 1
        if event["stage"] == "model_output":
            tokens += event.get("response", {}).get("usage", {}).get("total_tokens", 0)
    return dict(
        model_calls_started=counts["model_input"],
        model_calls_completed=counts["model_output"],
        model_calls_failed_or_interrupted=counts["model_error"],
        http_attempts=counts["groq_request_start"],
        retries_scheduled=counts["groq_retry"],
        provider_errors=dict(statuses),
        observed_wait_seconds=round(waits, 2),
        reported_tokens=tokens,
        incomplete_event_lines=counts["incomplete_event_lines"],
    )
