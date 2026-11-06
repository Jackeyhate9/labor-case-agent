def envelope(response, status=200):
    assert response.status_code == status, response.text
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def confirmed_fact(client, case_id, text="2026年2月欠薪6000元"):
    evidence = envelope(
        client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": ("fact.txt", text.encode("utf-8"), "text/plain")},
        ),
        201,
    )
    processed = envelope(client.post(f"/api/evidence/{evidence['id']}/process"))
    fact = processed["candidate_facts"][0]
    envelope(client.post(f"/api/facts/{fact['id']}/confirm"))
    return evidence, fact


def test_existing_cases_remain_searchable_when_embedding_is_disabled(client, case_id, monkeypatch):
    _, fact = confirmed_fact(client, case_id)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "disabled")

    result = envelope(client.get(f"/api/cases/{case_id}/search", params={"q": "欠薪"}))
    assert result["mode"] == "lexical"
    assert result["embedding_model_version"] is None
    assert result["results"][0]["entity_type"] == "fact"
    assert result["results"][0]["entity_id"] == fact["id"]
    assert "欠薪" in result["results"][0]["text"]


def test_real_bge_m3_indexes_versioned_vectors_and_searches(client, case_id, monkeypatch):
    from pathlib import Path
    import sys

    model = Path(r"D:\AI\Vibe code\memoira-ai\models\BAAI\bge-m3")
    if not (model / "pytorch_model.bin").is_file():
        import pytest

        pytest.skip("complete local BGE-M3 checkpoint is not available")
    _, fact = confirmed_fact(client, case_id, "2026年2月公司拖欠工资6000元")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "bge-m3")
    monkeypatch.setenv("BGE_M3_MODEL_PATH", str(model))
    monkeypatch.setenv("EMBEDDING_PYTHON", sys.executable)

    indexed = envelope(client.post(f"/api/cases/{case_id}/embeddings/reindex"))
    assert indexed["embedding_model_version"] == "bge-m3-v1"
    assert indexed["indexed"] == 1
    assert indexed["dimensions"] == 1024

    result = envelope(client.get(f"/api/cases/{case_id}/search", params={"q": "未支付的薪资"}))
    assert result["mode"] == "semantic"
    assert result["embedding_model_version"] == "bge-m3-v1"
    assert result["results"][0]["entity_id"] == fact["id"]
    assert result["results"][0]["score"] > 0


def test_real_nemotron_indexes_2048_dimension_versioned_vectors(client, case_id, monkeypatch):
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    model = root / "models" / "Nemotron-3-Embed-1B-BF16"
    runtime = root / ".venv-moss" / "Scripts" / "python.exe"
    if not (model / "model.safetensors").is_file() or not runtime.is_file():
        import pytest

        pytest.skip("local Nemotron checkpoint or Transformers 5 runtime is unavailable")
    _, fact = confirmed_fact(client, case_id, "2026年2月公司拖欠工资6000元")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "nemotron-3-embed-1b")
    monkeypatch.setenv("NEMOTRON_EMBED_MODEL_PATH", str(model))
    monkeypatch.setenv("EMBEDDING_PYTHON", str(runtime))

    indexed = envelope(client.post(f"/api/cases/{case_id}/embeddings/reindex"))
    assert indexed["provider"] == "nemotron-3-embed-1b"
    assert indexed["embedding_model_version"] == "nemotron-v1"
    assert indexed["indexed"] == 1
    assert indexed["dimensions"] == 2048

    result = envelope(client.get(f"/api/cases/{case_id}/search", params={"q": "未支付的薪资"}))
    assert result["mode"] == "semantic"
    assert result["embedding_model_version"] == "nemotron-v1"
    assert result["results"][0]["entity_id"] == fact["id"]
    assert result["results"][0]["score"] > 0


def test_evidence_graph_traces_evidence_fact_timeline_and_claim(client, case_id):
    evidence, fact = confirmed_fact(client, case_id)
    timeline = envelope(client.post(f"/api/cases/{case_id}/timeline/rebuild"))[0]
    claim = envelope(
        client.post(
            f"/api/cases/{case_id}/claims",
            json={"claim_type": "salary_arrears", "title": "支付拖欠工资", "amount": "6000"},
        ),
        201,
    )

    graph = envelope(client.get(f"/api/cases/{case_id}/graph"))
    node_ids = {node["id"] for node in graph["nodes"]}
    assert {evidence["id"], fact["id"], timeline["id"], claim["id"]} <= node_ids
    edges = {(edge["source"], edge["relationship"], edge["target"]) for edge in graph["edges"]}
    assert (evidence["id"], "PROVES", fact["id"]) in edges
    assert (fact["id"], "SUPPORTS_TIMELINE", timeline["id"]) in edges
    assert (fact["id"], "SUPPORTS_CLAIM", claim["id"]) in edges
