from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "python" in data["supported_languages"]
    assert "java" in data["supported_languages"]


def test_languages_endpoint():
    resp = client.get("/api/languages")
    assert resp.status_code == 200
    assert set(resp.json()["languages"]) == {"python", "java"}


def test_samples_endpoint_returns_runnable_samples():
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    samples = resp.json()
    assert len(samples) >= 2
    for s in samples:
        assert s["code"].strip()


def test_review_endpoint_python():
    resp = client.post(
        "/api/review",
        json={"code": "def add(a, b):\n    return a + b\n", "language": "python"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "python"
    assert "summary" in data
    assert "agents" in data
    assert len(data["agents"]) == 5


def test_review_endpoint_java():
    resp = client.post(
        "/api/review",
        json={
            "code": "public class A { public static void main(String[] a) {} }",
            "language": "java",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["language"] == "java"


def test_review_endpoint_rejects_empty_code():
    resp = client.post("/api/review", json={"code": "   ", "language": "python"})
    assert resp.status_code == 422


def test_review_endpoint_rejects_invalid_language():
    resp = client.post("/api/review", json={"code": "x = 1", "language": "ruby"})
    assert resp.status_code == 422


def test_review_endpoint_reports_syntax_error():
    resp = client.post(
        "/api/review", json={"code": "def broken(:\n    pass\n", "language": "python"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["errors"] == 1
    assert any(f["category"] == "syntax" for f in data["findings"])
