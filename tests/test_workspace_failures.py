"""File limits, invalid documents, restart recovery and closed upload streams."""

import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from test_connected_workspace import connected as connected
from workspace_helpers import TinyProvider, upload_ready

from app.api.workspace.service import ConnectedWorkspaceService
from app.api.workspace_contracts import ProcessingJob
from app.main import create_app


def test_file_size_limit_removes_incomplete_upload(connected):
    client, service = connected
    service.settings.upload_max_file_bytes = 4
    response = client.post("/api/sessions", files=[("files", ("Bid1/a.html", b"too large"))])
    assert response.status_code == 413
    assert not list((service.settings.storage_dir / "uploads").glob("*"))
    assert not service.jobs.path.exists()


def test_total_size_and_file_count_limits(connected):
    client, service = connected
    service.settings.upload_max_bytes = 5
    files = [("files", ("Bid1/a.html", b"abc")), ("files", ("Bid1/b.html", b"def"))]
    assert client.post("/api/sessions", files=files).status_code == 413
    service.settings.upload_max_files = 1
    assert client.post("/api/sessions", files=files).status_code == 413
    assert not list((service.settings.storage_dir / "uploads").glob("*"))


def test_invalid_pdf_becomes_failed_job(connected):
    client, service = connected
    response = client.post("/api/sessions", files=[("files", ("Bid1/broken.pdf", b"not a pdf"))])
    assert response.status_code == 202
    job_id = response.json()["id"]
    for _ in range(300):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "processing":
            break
        time.sleep(0.01)
    assert job["status"] == "failed"
    assert job["discovery_id"] is None
    assert not list((service.settings.vector_db_dir.parent / "manifests").glob("*.json"))


def test_interrupted_job_is_failed_after_restart(connected):
    client, service = connected
    job_id = uuid4()
    service.jobs.save(ProcessingJob(id=job_id, status="processing"))
    response = client.get(f"/api/jobs/{job_id}")
    assert response.json()["status"] == "failed"
    assert "restart" in response.json()["detail"]
    assert service.jobs.get(job_id).status == "failed"
    assert client.get(f"/api/jobs/{uuid4()}").status_code == 404


def test_ready_upload_can_be_searched_after_restart(connected):
    client, service = connected
    job = upload_ready(client)
    restarted = ConnectedWorkspaceService(service.settings)
    restarted.runtime.provider = TinyProvider()
    app = create_app()
    app.state.workspace_service = restarted
    with TestClient(app) as next_client:
        assert next_client.get(f"/api/jobs/{job['id']}").json()["status"] == "ready"
        result = next_client.post(
            "/api/sessions/search",
            json={"question": "Delivery", "discovery_ids": [job["discovery_id"]]},
        )
        assert result.status_code == 200
        assert result.json()["sources"][0]["discovery_id"] == job["discovery_id"]
    assert restarted.jobs.get(UUID(job["id"])).status == "ready"


def test_pdf_upload_retains_page_citations_and_notices(connected, sample_pdf):
    client, service = connected
    response = client.post(
        "/api/sessions",
        files=[("files", ("Bid1/rfp.pdf", sample_pdf.file_path.read_bytes(), "application/pdf"))],
    )
    assert response.status_code == 202
    for _ in range(300):
        job = client.get(f"/api/jobs/{response.json()['id']}").json()
        if job["status"] != "processing":
            break
        time.sleep(0.01)
    assert job["status"] == "ready", job
    result = client.post(
        "/api/sessions/search",
        json={"question": "Delivery", "discovery_ids": [job["discovery_id"]], "top_k": 20},
    )
    assert result.status_code == 200
    assert result.json()["sources"][0]["file"] == "rfp.pdf"
    assert all(source["page"] for source in result.json()["sources"])
    assert "parsing notices" in job["detail"]


def test_status_polling_stays_responsive_during_indexing(connected):
    from threading import Event

    client, service = connected
    started, release = Event(), Event()
    index = service.runtime.index

    def slow_index(folder):
        started.set()
        assert release.wait(timeout=5)
        return index(folder)

    service.runtime.index = slow_index
    try:
        response = client.post(
            "/api/sessions",
            files=[("files", ("Bid1/rfp.html", b"<p>Delivery within 45 days.</p>"))],
        )
        assert response.status_code == 202
        assert started.wait(timeout=2)
        job = client.get(f"/api/jobs/{response.json()['id']}")
        assert job.status_code == 200
        assert job.json()["status"] == "processing"
        assert client.get("/health").status_code == 200
    finally:
        release.set()
