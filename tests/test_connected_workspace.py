"""Exercise the connected browser API with real pipeline/store and offline models."""

import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("chromadb")
pytest.importorskip("langgraph")
from workspace_helpers import ScriptedModel, TinyProvider, upload_ready

from app.api.workspace.service import ConnectedWorkspaceService
from app.config import Settings
from app.main import create_app


@pytest.fixture
def connected(tmp_path):
    settings = Settings(
        storage_dir=tmp_path / "storage",
        vector_db_dir=tmp_path / "storage/chroma",
        output_dir=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        groq_api_key="",
        search_rerank=False,  # This suite uses scripted models; reranking has its own checks.
    )
    service = ConnectedWorkspaceService(settings)
    service.runtime.provider = TinyProvider()
    service.runtime._model = ScriptedModel()
    app = create_app()
    app.state.workspace_service = service
    with TestClient(app) as client:
        yield client, service


def test_upload_search_answer_and_persistence(connected):
    client, service = connected
    job = upload_ready(client)
    upload_id = job["discovery_id"]
    saved = service.settings.storage_dir / "uploads" / job["id"] / "Bid1/rfp.html"
    assert saved.is_file()
    manifest = service.settings.vector_db_dir.parent / "manifests" / f"{upload_id}.json"
    assert json.loads(manifest.read_text())["stored_chunks"] > 0
    for mode in ["search", "ask"]:
        response = client.post(
            f"/api/sessions/{mode}", json={"question": "Delivery?", "discovery_ids": [upload_id]}
        )
        assert response.status_code == 200, response.text
        assert response.json()["sources"][0]["discovery_id"] == upload_id
        assert response.json()["sources"][0]["folder_name"] == "Bid1"
    assert len(service.runtime._model.calls) == 2
    assert list(service.settings.log_dir.glob("api-*.json"))
    restarted = ConnectedWorkspaceService(service.settings)
    assert restarted.jobs.get(UUID(job["id"])).status == "ready"


def test_two_same_named_uploads_have_distinct_ids_and_citations(connected):
    client, service = connected
    first, second = upload_ready(client), upload_ready(client)
    assert first["discovery_id"] != second["discovery_id"]
    ids = [first["discovery_id"], second["discovery_id"]]
    response = client.post(
        "/api/sessions/ask", json={"question": "Compare delivery", "discovery_ids": ids}
    )
    assert response.status_code == 200
    assert {source["discovery_id"] for source in response.json()["sources"]} == set(ids)
    assert len(service.runtime._model.calls) == 2


def test_unknown_upload_is_rejected_before_model_call(connected):
    client, service = connected
    response = client.post(
        "/api/sessions/ask", json={"question": "Deadline?", "discovery_ids": [str(uuid4())]}
    )
    assert response.status_code == 404
    assert not service.runtime._model.calls


def test_website_supports_conditional_second_qa_call(connected, monkeypatch):
    client, service = connected
    job = upload_ready(client)
    model = service.runtime._model
    original = model.complete

    def complete(messages, **kwargs):
        schema = kwargs["response_format"]["json_schema"]["name"]
        if schema == "answer_or_search":
            model.calls.append(messages)
            content = dict(
                action="search_more",
                status="not_found",
                answer="",
                source_chunk_ids=[],
                search_queries=["Warranty requirements"],
                missing_information=["Warranty"],
            )
            return dict(message={"content": json.dumps(content)}, usage={}, finish_reason="stop")
        return original(messages, **kwargs)

    monkeypatch.setattr(model, "complete", complete)
    response = client.post(
        "/api/sessions/ask",
        json={
            "question": "Delivery and warranty?",
            "discovery_ids": [job["discovery_id"]],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["discovery_id"] == job["discovery_id"]
    assert len(model.calls) == 3  # Planner + decision + final answer.


def test_search_filters_and_legacy_single_upload_route(connected):
    client, service = connected
    job = upload_ready(client)
    response = client.post(
        f"/api/sessions/{job['discovery_id']}/search",
        json={"question": "Delivery", "top_k": 20, "file_name": "missing.pdf"},
    )
    assert response.status_code == 200
    assert response.json() == {"answer": "Not found in documents", "sources": []}
    assert not service.runtime._model.calls


def test_model_failure_has_http_error_and_trace(connected):
    client, service = connected
    job = upload_ready(client)
    service.runtime._model.fail = True
    response = client.post(
        "/api/sessions/ask", json={"question": "Deadline?", "discovery_ids": [job["discovery_id"]]}
    )
    assert response.status_code == 504
    assert list(service.settings.log_dir.glob("api-*.json"))


def test_search_works_without_groq_key_and_ask_reports_missing_key(connected):
    client, service = connected
    job = upload_ready(client)
    service.runtime._model = None
    body = {"question": "Delivery", "discovery_ids": [job["discovery_id"]]}
    assert client.post("/api/sessions/search", json=body).status_code == 200
    response = client.post("/api/sessions/ask", json=body)
    assert response.status_code == 503
    assert "RFP_GROQ_API_KEY" in response.json()["detail"]


def test_main_graph_extraction_saves_fields_and_returns_citations(connected):
    client, service = connected
    job = upload_ready(client)
    response = client.post(
        "/api/sessions/ask",
        json={"question": "Extract all fields", "discovery_ids": [job["discovery_id"]]},
    )
    assert response.status_code == 200, response.text
    output = service.settings.output_dir / f"fields-{job['discovery_id']}.json"
    assert len(json.loads(output.read_text())["fields"]) == 20
    assert response.json()["sources"]
    assert len(service.runtime._model.calls) == 9


def test_open_existing_id_without_reindexing_or_model_calls(connected, monkeypatch):
    client, service = connected
    job = upload_ready(client)
    calls = len(service.runtime._model.calls)

    def forbidden(*args, **kwargs):
        raise AssertionError("Opening an ID must not embed or index")

    monkeypatch.setattr(service.runtime, "index", forbidden)
    monkeypatch.setattr(service.runtime.provider, "embed_documents", forbidden)
    monkeypatch.setattr(service.runtime.provider, "embed_query", forbidden)
    response = client.get(f"/api/sessions/{job['discovery_id']}")
    assert response.status_code == 200, response.text
    assert response.json()["folder_name"] == "Bid1"
    assert response.json()["stored_chunks"] > 0
    assert response.json()["files"][0]["relative_path"] == "rfp.html"
    assert len(service.runtime._model.calls) == calls


def test_open_existing_id_rejects_deleted_vectors(connected):
    client, service = connected
    job = upload_ready(client)
    service.runtime.store.collection.delete(where={"discovery_id": job["discovery_id"]})
    response = client.get(f"/api/sessions/{job['discovery_id']}")
    assert response.status_code == 409
    assert "removed" in response.json()["detail"]


def test_open_existing_id_rejects_other_model_collection(connected):
    client, service = connected
    job = upload_ready(client)
    service.settings.vector_collection = "other-model"
    response = client.get(f"/api/sessions/{job['discovery_id']}")
    assert response.status_code == 409


def test_open_existing_id_rejects_unknown_or_invalid_id(connected):
    client, _ = connected
    assert client.get(f"/api/sessions/{uuid4()}").status_code == 404
    assert client.get("/api/sessions/not-a-uuid").status_code == 422
