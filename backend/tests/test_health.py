from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_requires_bearer_token() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_event_mutations_require_authentication() -> None:
    with TestClient(app) as client:
        create_response = client.post(
            "/api/v1/events",
            json={"name": "Private event"},
        )
        delete_response = client.delete("/api/v1/events/event-id")
    assert create_response.status_code == 401
    assert delete_response.status_code == 401


def test_upload_routes_require_authentication() -> None:
    with TestClient(app) as client:
        events_response = client.get("/api/v1/photographer/events")
        upload_response = client.post(
            "/api/v1/events/event-id/uploads",
            json={"filename": "photo.jpg", "content_type": "image/jpeg"},
        )
    assert events_response.status_code == 401
    assert upload_response.status_code == 401


def test_role_changes_require_authentication() -> None:
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/me/role",
            json={"role": "organizer"},
        )
    assert response.status_code == 401
