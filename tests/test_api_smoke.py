from fastapi.testclient import TestClient

from api import main as api_main


client = TestClient(api_main.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_configured_local_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_create_session(monkeypatch):
    monkeypatch.setattr(api_main, "create_session", lambda: {"thread_id": "test-thread"})

    response = client.post("/sessions")

    assert response.status_code == 200
    assert response.json() == {"thread_id": "test-thread"}


def test_chat_stream_basic_request_structure(monkeypatch):
    def fake_build_config(thread_id):
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 1}

    async def fake_iter_chat_event_lines(user_message, config, model_name):
        assert user_message == "帮我规划福州一日游"
        assert config["configurable"]["thread_id"] == "test-thread"
        assert model_name == "test-model"
        yield '{"type":"done"}\n'

    monkeypatch.setattr(api_main, "build_config", fake_build_config)
    monkeypatch.setattr(api_main, "iter_chat_event_lines", fake_iter_chat_event_lines)

    response = client.post(
        "/chat/stream",
        json={
            "thread_id": "test-thread",
            "message": "帮我规划福州一日游",
            "model_name": "test-model",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.text == '{"type":"done"}\n'


def test_chat_stream_rejects_missing_required_fields():
    response = client.post("/chat/stream", json={"message": "缺少会话"})

    assert response.status_code == 422
