"""Replay successful operations in one extraction job without repeating provider calls."""

import hashlib
import json

from app.api.workspace.files import save_json


class SavedOperation:
    def __init__(self, target, directory, name, progress):
        self.target = target
        self.directory = directory
        self.name = name
        self.progress = progress

    def __getattr__(self, name):
        return getattr(self.target, name)

    def invoke(self, arguments, operation):
        encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        key = hashlib.sha256(encoded.encode()).hexdigest()
        path = self.directory / f"{self.name}-{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        self.progress(f"Running {self.name} step")
        result = operation()
        if self.name == "model":
            # Do not replay incomplete or non-JSON responses from structured calls.
            json.loads(result["message"]["content"])
            if result.get("finish_reason") == "length":
                raise ValueError("Model output was truncated")
            self.check_response(arguments, result)
        save_json(path, json.dumps(result, ensure_ascii=False))
        return result

    def check_response(self, arguments, result):
        from app.agents.extraction.models.fields import ExtractionDraft
        from app.agents.extraction.models.validation import ValidationReport

        schema = arguments.get("response_format", {}).get("json_schema", {})
        contracts = {"bid_fields": ExtractionDraft, "field_validation": ValidationReport}
        contract = contracts.get(schema.get("name"))
        if contract:
            contract.model_validate_json(result["message"]["content"])


class SavedModel(SavedOperation):
    def complete(self, messages, **kwargs):
        return self.invoke(
            {"messages": messages, **kwargs},
            lambda: self.target.complete(messages, **kwargs),
        )


class SavedSearch(SavedOperation):
    def run(self, arguments):
        return self.invoke(arguments, lambda: self.target.run(arguments))
