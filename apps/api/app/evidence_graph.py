from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def build_evidence_graph(db: Session, case_id: str) -> dict[str, object]:
    facts = db.scalars(
        select(models.ExtractedFact).where(
            models.ExtractedFact.case_id == case_id,
            models.ExtractedFact.review_status == "user_confirmed",
        )
    ).all()
    evidence_ids = {fact.source_evidence_id for fact in facts if fact.source_evidence_id}
    evidence = db.scalars(select(models.Evidence).where(models.Evidence.id.in_(evidence_ids))).all() if evidence_ids else []
    timeline = db.scalars(select(models.TimelineEvent).where(models.TimelineEvent.case_id == case_id)).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.case_id == case_id)).all()

    nodes = []
    for item in evidence:
        nodes.append({"id": item.id, "type": "Evidence", "label": item.evidence_number, "review_status": item.review_status})
    for fact in facts:
        nodes.append({"id": fact.id, "type": "Fact", "label": fact.user_corrected_value or fact.normalized_value or fact.object_value, "review_status": fact.review_status, "source_region_id": fact.source_region_id})
    for event in timeline:
        nodes.append({"id": event.id, "type": "TimelineEvent", "label": event.title, "date": event.event_date.isoformat() if event.event_date else None})
    for claim in claims:
        nodes.append({"id": claim.id, "type": "Claim", "label": claim.title, "status": claim.status})

    edges = []
    for fact in facts:
        if fact.source_evidence_id:
            edges.append({"source": fact.source_evidence_id, "relationship": "PROVES", "target": fact.id, "source_region_id": fact.source_region_id})
    for event in timeline:
        edges.append({"source": event.source_fact_id, "relationship": "SUPPORTS_TIMELINE", "target": event.id})
    for claim in claims:
        for fact in facts:
            if fact.fact_type == claim.claim_type:
                edges.append({"source": fact.id, "relationship": "SUPPORTS_CLAIM", "target": claim.id})
    return {"nodes": nodes, "edges": edges, "confirmed_only": True, "node_count": len(nodes), "edge_count": len(edges)}
