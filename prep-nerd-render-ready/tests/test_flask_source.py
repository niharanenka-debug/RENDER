import app as server
from core.db import Database


def _workspace(monkeypatch, tmp_path):
    database = Database(tmp_path / "workspace.db")
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setattr(server, "api_key", lambda: None)
    monkeypatch.setattr(server, "_safe_url", lambda url: url)
    monkeypatch.setattr(
        server,
        "extract_url",
        lambda url: (
            "Photosynthesis uses light energy and chlorophyll to help plants produce glucose.",
            url,
        ),
    )
    server.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    client = server.app.test_client()
    token = client.get("/api/bootstrap").get_json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


def test_homepage_and_assets_are_served(monkeypatch, tmp_path):
    client, _ = _workspace(monkeypatch, tmp_path)
    page = client.get("/")
    assert page.status_code == 200
    assert b"Choose a source" in page.data
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_new_url_replaces_latest_source_and_failure_keeps_current(monkeypatch, tmp_path):
    client, headers = _workspace(monkeypatch, tmp_path)
    first = client.post(
        "/api/sources",
        json={"kind": "text", "title": "Old notes", "text": "Old source contents are long enough."},
        headers=headers,
    )
    assert first.status_code == 201
    old_source = first.get_json()["source"]

    newer = client.post(
        "/api/sources", json={"kind": "url", "url": "https://example.com/new"}, headers=headers
    )
    assert newer.status_code == 201
    new_source = newer.get_json()["source"]
    assert new_source["id"] != old_source["id"]
    assert new_source["kind"] == "url"
    assert "Photosynthesis" in new_source["content"]
    assert client.get("/api/bootstrap").get_json()["active_source"]["id"] == new_source["id"]

    monkeypatch.setattr(server, "extract_url", lambda _url: (_ for _ in ()).throw(RuntimeError("fetch failed")))
    failed = client.post(
        "/api/sources", json={"kind": "url", "url": "https://example.com/bad"}, headers=headers
    )
    assert failed.status_code == 422
    assert client.get("/api/bootstrap").get_json()["active_source"]["id"] == new_source["id"]


def test_activating_latest_choice_updates_active_source_for_all_tools(monkeypatch, tmp_path):
    client, headers = _workspace(monkeypatch, tmp_path)
    first = client.post(
        "/api/sources",
        json={"kind": "text", "title": "Source one", "text": "First source has material for study."},
        headers=headers,
    ).get_json()["source"]
    second = client.post(
        "/api/sources",
        json={"kind": "text", "title": "Source two", "text": "Second source has different material."},
        headers=headers,
    ).get_json()["source"]

    assert client.post(f"/api/sources/{first['id']}/activate", json={}, headers=headers).status_code == 200
    assert client.get("/api/bootstrap").get_json()["active_source"]["id"] == first["id"]

    class FakeGemini:
        def __init__(self, **_kwargs):
            pass

        def analyze(self, _task, content, _depth):
            return f"Analysis used: {content}"

    monkeypatch.setattr(server, "GeminiService", FakeGemini)
    generated = client.post(
        "/api/generate",
        json={"action": "summary", "title": "Current-source summary"},
        headers=headers,
    )
    assert generated.status_code == 201
    artifact = generated.get_json()["artifact"]
    assert artifact["payload"]["source_id"] == first["id"]
    assert "First source" in artifact["payload"]["text"]
    assert second["id"] != first["id"]


def test_workspace_data_isolated_by_browser_session(monkeypatch, tmp_path):
    first_client, first_headers = _workspace(monkeypatch, tmp_path)
    created = first_client.post(
        "/api/sources",
        json={"kind": "text", "title": "Private to this cookie", "text": "Source for one anonymous workspace."},
        headers=first_headers,
    )
    assert created.status_code == 201

    second_client = server.app.test_client()
    second_bootstrap = second_client.get("/api/bootstrap").get_json()
    assert second_bootstrap["sources"] == []
    assert second_bootstrap["active_source"] is None


def test_youtube_requires_gemini_key_without_changing_active_source(monkeypatch, tmp_path):
    client, headers = _workspace(monkeypatch, tmp_path)
    existing = client.post(
        "/api/sources",
        json={"kind": "text", "title": "Current notes", "text": "Keep this source active after failure."},
        headers=headers,
    ).get_json()["source"]
    response = client.post(
        "/api/sources",
        json={"kind": "url", "url": "https://www.youtube.com/watch?v=public-video"},
        headers=headers,
    )
    assert response.status_code == 503
    assert "Gemini API key is required" in response.get_json()["error"]
    assert client.get("/api/bootstrap").get_json()["active_source"]["id"] == existing["id"]
