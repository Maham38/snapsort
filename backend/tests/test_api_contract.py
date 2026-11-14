from fastapi.testclient import TestClient

from app.main import app


def test_openapi_exposes_protected_phase_endpoints() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = {
        "/api/v1/attendee/events",
        "/api/v1/attendee/events/{event_id}/gallery",
        "/api/v1/events/{event_id}/matching-jobs",
        "/api/v1/matching-jobs/{job_id}/results",
        "/api/v1/photos/{photo_id}/favorite",
    }
    assert expected <= paths.keys()


def test_gallery_and_favorite_routes_require_authentication() -> None:
    with TestClient(app) as client:
        responses = [
            client.get("/api/v1/attendee/events/event-id/gallery"),
            client.post("/api/v1/photos/photo-id/favorite"),
            client.delete("/api/v1/photos/photo-id/favorite"),
        ]

    assert [response.status_code for response in responses] == [401, 401, 401]
