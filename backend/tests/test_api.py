"""FastAPI 接口测试。"""

from fastapi.testclient import TestClient

from cookkg.api import create_app


def test_health(engine):
    client = TestClient(create_app(engine))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_recommend_endpoint(engine):
    client = TestClient(create_app(engine))
    payload = {
        "have": ["鸡蛋", "土豆", "西红柿"],
        "pantry": ["盐", "食用油", "生抽"],
        "exclude": ["辣椒"],
        "count": 2,
        "max_buy": 2,
        "limit": 5,
    }
    resp = client.post("/recommend", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    assert data["plans"]


def test_recommend_validates_count(engine):
    client = TestClient(create_app(engine))
    resp = client.post("/recommend", json={"have": [], "count": 5})
    assert resp.status_code == 422
