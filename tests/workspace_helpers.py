"""Offline boundaries; parsing, chunking, Chroma, API and graphs stay real."""

import json
import time

from app.schemas.embeddings import EmbeddingInfo


class TinyProvider:
    info = EmbeddingInfo(
        provider="test",
        model="test",
        revision="fixed",
        dimensions=2,
        max_tokens=100,
        library_version="test",
    )

    def embed_documents(self, texts):
        return [[1.0, 0.0] for text in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


class ScriptedModel:
    def __init__(self):
        self.fail = False
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        if self.fail:
            raise TimeoutError()
        schema = kwargs["response_format"]["json_schema"]["name"]
        if schema == "workflow_choice":
            task = "extraction" if "Extract" in messages[-1]["content"] else "qa"
            content = {"task": task, "message": None}
        elif schema in ("document_answer", "answer_or_search"):
            if schema == "answer_or_search":
                evidence = json.loads(messages[-1]["content"])
            else:
                message = next(
                    item for item in messages if item["content"].startswith("Retrieved evidence:\n")
                )
                evidence = json.loads(message["content"].split("Retrieved evidence:\n")[1])
            content = {
                "status": "found",
                "answer": "Delivery within 45 days.",
                "source_chunk_ids": [item["chunk_id"] for item in evidence],
            }
            if schema == "answer_or_search":
                content.update(action="answer", search_queries=[], missing_information=[])
        elif schema == "field_validation":
            fields = json.loads(messages[1]["content"])["fields"]
            content = {
                "fields": [
                    {"name": field["name"], "decision": "accepted", "reason": "Scripted support"}
                    for field in fields
                ]
            }
        else:
            evidence = json.loads(messages[-1]["content"])
            names = [
                line[2:].split(":", 1)[0]
                for line in messages[0]["content"].splitlines()
                if line.startswith("- ")
            ]
            content = {
                "fields": [
                    {
                        "name": name,
                        "value": "Offline test value",
                        "confidence": 0.8,
                        "notes": None,
                        "source_chunk_ids": [evidence[0]["chunk_id"]],
                    }
                    for name in names
                ]
            }
        return {"message": {"content": json.dumps(content)}, "usage": {}, "finish_reason": "stop"}


def upload_ready(client, name="Bid1", text="Delivery within 45 days. Warranty: 3 years."):
    response = client.post(
        "/api/sessions",
        files=[
            ("files", (f"{name}/rfp.html", f"<html><body><p>{text}</p></body></html>".encode()))
        ],
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    for _ in range(300):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "processing":
            assert job["status"] == "ready", job
            assert job["discovery_id"] == job["session_id"]
            return job
        time.sleep(0.01)
    raise AssertionError("Job did not finish")
