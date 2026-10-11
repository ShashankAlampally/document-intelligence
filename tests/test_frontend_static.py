"""Verify the single-server frontend/API arrangement used by Docker."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_frontend_assets_do_not_shadow_api(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>RFP workspace</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('workspace')")
    monkeypatch.setenv("RFP_FRONTEND_DIST_DIR", str(tmp_path))
    with TestClient(create_app()) as client:
        assert "RFP workspace" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        assert "/api/sessions" in client.get("/openapi.json").json()["paths"]
        assert client.get("/api/unknown").status_code == 404
        assert client.get("/.env").status_code == 404


def test_api_can_start_without_frontend_build(tmp_path, monkeypatch):
    monkeypatch.setenv("RFP_FRONTEND_DIST_DIR", str(tmp_path / "missing"))
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 404
