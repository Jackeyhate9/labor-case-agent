from __future__ import annotations

import os
import hashlib
import json
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .providers.embedding import embedding_configuration, encode_texts
from .services import ServiceError


def reindex_case_embeddings(db: Session, case_id: str) -> dict[str, object]:
    configuration, reason = embedding_configuration()
    if configuration is None:
        raise ServiceError("EMBEDDING_PROVIDER_UNAVAILABLE", f"Embedding provider unavailable: {reason}", 503)
    facts = db.scalars(
        select(models.ExtractedFact).where(
            models.ExtractedFact.case_id == case_id,
            models.ExtractedFact.review_status == "user_confirmed",
        )
    ).all()
    texts = [fact.user_corrected_value or fact.normalized_value or fact.object_value for fact in facts]
    vectors = encode_texts(configuration, texts, role="passage") if texts else []
    db.query(models.EvidenceEmbedding).filter(
        models.EvidenceEmbedding.case_id == case_id,
        models.EvidenceEmbedding.embedding_model_version == configuration.model_version,
    ).delete()
    for fact, text, vector in zip(facts, texts, vectors):
        db.add(
            models.EvidenceEmbedding(
                case_id=case_id,
                entity_type="fact",
                entity_id=fact.id,
                embedding_model_version=configuration.model_version,
                dimensions=len(vector),
                vector_json=json.dumps(vector),
                content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    db.flush()
    return {"provider": configuration.provider, "embedding_model_version": configuration.model_version, "indexed": len(vectors), "dimensions": len(vectors[0]) if vectors else 0}


def search_case(db: Session, case_id: str, query: str) -> dict[str, object]:
    query = query.strip()
    if not query:
        return {"mode": "lexical", "embedding_model_version": None, "results": []}
    facts = db.scalars(
        select(models.ExtractedFact).where(
            models.ExtractedFact.case_id == case_id,
            models.ExtractedFact.review_status == "user_confirmed",
        )
    ).all()
    results = []
    for fact in facts:
        text = fact.user_corrected_value or fact.normalized_value or fact.object_value
        if query.casefold() in text.casefold():
            results.append(
                {
                    "entity_type": "fact",
                    "entity_id": fact.id,
                    "text": text,
                    "score": 1.0,
                    "source_evidence_id": fact.source_evidence_id,
                    "source_region_id": fact.source_region_id,
                }
            )
    configuration, _ = embedding_configuration()
    if configuration is None:
        return {"mode": "lexical", "embedding_model_version": None, "results": results}
    embeddings = db.scalars(
        select(models.EvidenceEmbedding).where(
            models.EvidenceEmbedding.case_id == case_id,
            models.EvidenceEmbedding.embedding_model_version == configuration.model_version,
        )
    ).all()
    if not embeddings:
        return {"mode": "lexical_fallback", "embedding_model_version": configuration.model_version, "results": results}
    query_vector = encode_texts(configuration, [query], role="query")[0]
    fact_by_id = {fact.id: fact for fact in facts}
    semantic = []
    for embedding in embeddings:
        fact = fact_by_id.get(embedding.entity_id)
        if not fact:
            continue
        vector = json.loads(embedding.vector_json)
        score = sum(left * right for left, right in zip(query_vector, vector))
        text = fact.user_corrected_value or fact.normalized_value or fact.object_value
        semantic.append({"entity_type": "fact", "entity_id": fact.id, "text": text, "score": round(score, 6), "source_evidence_id": fact.source_evidence_id, "source_region_id": fact.source_region_id})
    semantic.sort(key=lambda item: item["score"], reverse=True)
    return {"mode": "semantic", "embedding_model_version": configuration.model_version, "results": semantic}
