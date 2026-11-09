from fastapi.testclient import TestClient

from kart.app.api import app

client = TestClient(app)


def test_health_answers_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_describes_the_health_route() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
