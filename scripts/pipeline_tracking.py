"""Persist searches, model requests, HTTP retries and waits before returning."""

import json
from datetime import datetime, timezone
from time import perf_counter


class TrackingSearch:
    def __init__(self, search, directory):
        self.search = search
        self.directory = directory
        self.discovery_ids = search.discovery_ids
        self.number = 0

    def run(self, arguments):
        self.number += 1
        context = dict(search_id=self.number, request=arguments)
        append_event(self.directory, dict(stage="search_input", **context))
        print(
            f"  Search {self.number}: {arguments.get('field_name')}: {arguments['query']}",
            flush=True,
        )
        started = perf_counter()
        try:
            chunks = self.search.run(arguments)
        except BaseException as error:
            append_event(
                self.directory,
                dict(
                    stage="search_error",
                    **context,
                    error=type(error).__name__,
                    error_detail=str(error),
                    elapsed_seconds=perf_counter() - started,
                ),
            )
            raise
        append_event(
            self.directory,
            dict(
                stage="search",
                **context,
                chunks=chunks,
                elapsed_seconds=perf_counter() - started,
            ),
        )
        print(
            f"  Search {self.number}: {len(chunks)} chunks in {perf_counter() - started:.1f}s",
            flush=True,
        )
        return chunks

    def add_heading_context(self, evidence):
        return self.search.add_heading_context(evidence)


class TrackingModel:
    def __init__(self, model, directory):
        self.model = model
        self.directory = directory
        self.number = 0

    def complete(self, messages, **kwargs):
        self.number += 1
        schema = kwargs.get("response_format", {}).get("json_schema", {})
        context = dict(call_id=self.number, schema_name=schema.get("name"))
        append_event(
            self.directory,
            dict(
                stage="model_input",
                **context,
                messages=messages,
                response_format=kwargs.get("response_format"),
            ),
        )
        print(
            f"  Model call {self.number}: {schema.get('name')}; shared Groq pacing applies",
            flush=True,
        )
        limiter = getattr(self.model, "rate_limit", None)
        previous_sink = getattr(limiter, "event_sink", None)
        if limiter is not None:

            def save_groq_event(event):
                append_event(self.directory, {**event, **context})
                if previous_sink is not None:
                    previous_sink(event)

            limiter.event_sink = save_groq_event
        started = perf_counter()
        try:
            response = self.model.complete(messages, **kwargs)
        except BaseException as error:
            append_event(
                self.directory,
                dict(
                    stage="model_error",
                    **context,
                    error=type(error).__name__,
                    error_detail=str(error),
                    status_code=getattr(error, "status_code", None),
                    elapsed_seconds=perf_counter() - started,
                ),
            )
            raise
        else:
            append_event(
                self.directory,
                dict(
                    stage="model_output",
                    **context,
                    response=response,
                    elapsed_seconds=perf_counter() - started,
                ),
            )
            return response
        finally:
            if limiter is not None:
                limiter.event_sink = previous_sink


def append_event(directory, event):
    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {"timestamp_utc": datetime.now(timezone.utc).isoformat(), **event},
                ensure_ascii=False,
            )
            + "\n"
        )
