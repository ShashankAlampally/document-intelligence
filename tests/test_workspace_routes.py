"""Verify HTTP validation, explicit unwired behavior and adapter handoff."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.workspace_contracts import DocumentReply, ProcessingJob, SourcePassage
from app.api.workspace_service import WorkspaceService, get_workspace_service
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_workspace_service] = WorkspaceService
    with TestClient(app) as value:
        yield value


def test_health_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok"}
    schema = client.get("/openapi.json").json()
    assert "/api/sessions" in schema["paths"]
    assert (
        "multipart/form-data" in schema["paths"]["/api/sessions"]["post"]["requestBody"]["content"]
    )


@pytest.mark.parametrize("operation", ["ask", "search"])
def test_valid_query_returns_explicit_not_connected(client, operation):
    response = client.post(f"/api/sessions/{uuid4()}/{operation}", json={"question": "Deadline?"})
    assert response.status_code == 501
    assert response.json()["code"] == "workspace_not_connected"


def test_status_and_upload_not_connected(client):
    assert client.get(f"/api/jobs/{uuid4()}").status_code == 501
    response = client.post("/api/sessions", files=[("files", ("Bid1/rfp.pdf", b"sample"))])
    assert response.status_code == 501


@pytest.mark.parametrize("question", ["", "   ", "x" * 4001])
def test_invalid_question(client, question):
    assert (
        client.post(f"/api/sessions/{uuid4()}/ask", json={"question": question}).status_code == 422
    )


def test_invalid_ids_and_filters(client):
    assert client.get("/api/jobs/not-an-id").status_code == 422
    for extra in [{"top_k": 0}, {"doc_type": "unknown"}, {"addendum_number": 0}, {"extra": True}]:
        response = client.post(f"/api/sessions/{uuid4()}/search", json={"question": "SKU", **extra})
        assert response.status_code == 422


@pytest.mark.parametrize(
    "filename", ["../a.pdf", "/a.pdf", "Bid1/../a.pdf", "Bid1\\a.pdf", "Bid1/a.exe", "C:/a.pdf"]
)
def test_unsafe_or_unsupported_upload_name(client, filename):
    assert client.post("/api/sessions", files=[("files", (filename, b"sample"))]).status_code == 422


def test_duplicate_and_multiple_folder_uploads(client):
    for names in [
        ["Bid1/a.pdf", "Bid1/a.pdf"],
        ["Bid1/a.pdf", "Bid2/b.html"],
        ["Bid1/a.pdf", "b.pdf"],
    ]:
        response = client.post(
            "/api/sessions", files=[("files", (name, b"sample")) for name in names]
        )
        assert response.status_code == 422
    assert client.post("/api/sessions").status_code == 422


def test_service_can_be_connected_without_route_changes():
    session_id, job_id = uuid4(), uuid4()
    received = {}

    class Adapter(WorkspaceService):
        async def start_folder(self, files):
            received["files"] = [(file.filename, await file.read()) for file in files]
            return ProcessingJob(id=job_id, status="processing")

        async def get_job(self, requested_id):
            assert requested_id == job_id
            return ProcessingJob(id=job_id, status="ready", session_id=session_id)

        async def ask(self, requested_id, query):
            assert requested_id == session_id
            received["question"] = query.question
            return DocumentReply(
                answer="45 days",
                sources=[SourcePassage(file="a.pdf", page=2, text="Delivery within 45 days")],
            )

        async def search(self, requested_id, query):
            return await self.ask(requested_id, query)

    app = create_app()
    app.dependency_overrides[get_workspace_service] = Adapter
    with TestClient(app) as connected:
        response = connected.post("/api/sessions", files=[("files", ("Bid1/a.pdf", b"content"))])
        assert response.status_code == 202
        assert received["files"] == [("Bid1/a.pdf", b"content")]
        assert connected.get(f"/api/jobs/{job_id}").json()["session_id"] == str(session_id)
        for operation in ["ask", "search"]:
            response = connected.post(
                f"/api/sessions/{session_id}/{operation}", json={"question": " Delivery? "}
            )
            assert response.status_code == 200
            assert response.json()["sources"][0]["page"] == 2
        assert received["question"] == "Delivery?"


def test_ready_job_must_have_session_id():
    with pytest.raises(ValueError, match="session_id"):
        ProcessingJob(id=uuid4(), status="ready")


@pytest.mark.parametrize("operation", ["ask", "search"])
def test_selected_query_passes_all_ids_to_adapter(operation):
    first, second = uuid4(), uuid4()
    received = []

    class Adapter(WorkspaceService):
        async def ask_selected(self, query):
            received.extend(query.discovery_ids)
            return DocumentReply(
                answer="Comparison",
                sources=[
                    SourcePassage(
                        file="rfp.pdf", text="Warranty", folder_name="Bid2", discovery_id=second
                    )
                ],
            )

        async def search_selected(self, query):
            return await self.ask_selected(query)

    app = create_app()
    app.dependency_overrides[get_workspace_service] = Adapter
    with TestClient(app) as connected:
        response = connected.post(
            f"/api/sessions/{operation}",
            json={
                "question": "Compare warranties",
                "discovery_ids": [str(first), str(second), str(first)],
            },
        )
    assert response.status_code == 200
    assert received == [first, second]
    assert response.json()["sources"][0]["discovery_id"] == str(second)


@pytest.mark.parametrize("ids", [[], ["not-a-uuid"], [str(uuid4())] * 21])
def test_invalid_selected_uploads(client, ids):
    response = client.post("/api/sessions/ask", json={"question": "Compare", "discovery_ids": ids})
    assert response.status_code == 422


def test_selected_query_unconnected_is_explicit(client):
    response = client.post(
        "/api/sessions/ask",
        json={"question": "Compare", "discovery_ids": [str(uuid4()), str(uuid4())]},
    )
    assert response.status_code == 501


def test_ready_job_uses_discovery_id_and_keeps_legacy_alias():
    upload_id = uuid4()
    job = ProcessingJob(id=uuid4(), status="ready", discovery_id=upload_id)
    assert job.session_id == job.discovery_id == upload_id
    with pytest.raises(ValueError, match="alias"):
        ProcessingJob(id=uuid4(), status="ready", discovery_id=upload_id, session_id=uuid4())
