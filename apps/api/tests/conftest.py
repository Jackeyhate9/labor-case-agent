import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="labor-api-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_root / 'test.db'}"
os.environ["STORAGE_ROOT"] = str(_root / "cases")
os.environ["MAX_UPLOAD_BYTES"] = "1024"
os.environ["LLM_PROVIDER"] = "disabled"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def case_id(client):
    response = client.post("/api/cases", json={"title": "测试欠薪案件", "parties": [{"party_type": "worker", "name": "测试用户甲"}]})
    assert response.status_code == 201
    return response.json()["data"]["id"]

