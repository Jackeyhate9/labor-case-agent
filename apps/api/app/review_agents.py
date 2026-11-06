from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def confirmed_facts(db: Session, case_id: str) -> list[models.ExtractedFact]:
    return list(
        db.scalars(
            select(models.ExtractedFact).where(
                models.ExtractedFact.case_id == case_id,
                models.ExtractedFact.review_status == "user_confirmed",
            )
        ).all()
    )


def evidence_review(db: Session, case_id: str) -> dict[str, object]:
    facts = confirmed_facts(db, case_id)
    strengths = [
        {
            "title": fact.fact_type,
            "description": fact.user_corrected_value or fact.normalized_value or fact.object_value,
            "fact_ids": [fact.id],
            "source_evidence_ids": [fact.source_evidence_id] if fact.source_evidence_id else [],
        }
        for fact in facts
        if fact.source_evidence_id
    ]
    weak = [
        {
            "title": "missing_source_region",
            "description": "该已确认事实尚未回链到页内具体区域。",
            "fact_ids": [fact.id],
        }
        for fact in facts
        if fact.source_evidence_id and not fact.source_region_id
    ]
    conflict_groups: dict[str, list[str]] = {}
    for fact in facts:
        if fact.conflict_group_id:
            conflict_groups.setdefault(fact.conflict_group_id, []).append(fact.id)
    conflicts = [
        {"title": "confirmed_conflict", "description": "同一冲突组内存在多个已确认事实，需再次核对。", "fact_ids": ids}
        for ids in conflict_groups.values()
        if len(ids) > 1
    ]
    existing_types = {fact.fact_type for fact in facts}
    requirements = {
        "employment_start": "补充入职日期、招聘沟通、考勤或工作安排材料。",
        "salary_agreement": "补充工资约定、工资条或稳定转账记录。",
        "salary_payment": "补充银行流水及第三人代付关系说明。",
        "social_insurance": "补充社保缴费记录并核对开始、停缴时间。",
    }
    missing = [
        {"fact_type": fact_type, "suggestion": suggestion}
        for fact_type, suggestion in requirements.items()
        if fact_type not in existing_types
    ]
    return {
        "strengths": strengths,
        "weaknesses": weak,
        "conflicts": conflicts,
        "missing_materials": missing,
        "confirmed_facts_only": True,
        "invented_facts": False,
        "llm_used": False,
    }


def adversarial_review(db: Session, case_id: str) -> dict[str, object]:
    facts = confirmed_facts(db, case_id)
    text = "\n".join(fact.user_corrected_value or fact.normalized_value or fact.object_value for fact in facts)
    fact_types = {fact.fact_type for fact in facts}
    wages = db.scalars(select(models.WageEntry).where(models.WageEntry.case_id == case_id)).all()
    rules = [
        ("third_party_payment", "第三人代付可能被主张为借款、合作款或其他非工资款项。", any(wage.payer_relationship and wage.payer_relationship != "company" for wage in wages), "需核对付款主体、备注和沟通记录。"),
        ("project_cooperation", "对方可能主张双方属于项目合作而非劳动关系。", "management_instruction" not in fact_types, "应结合管理指令、考勤、报酬和组织从属性核验。"),
        ("rent_payment_relationship", "涉及房租或代付时，对方可能主张款项属于租赁结算。", "房租" in text, "需区分租金、工资和代付款项的日期、备注及主体。"),
        ("no_fixed_payday", "无固定发薪日可能被用于争议欠付起算时间。", not any("发薪日" in line for line in text.splitlines()), "补充工资约定、历史发放规律或催付记录。"),
        ("no_written_contract", "无书面劳动合同可能被用于否认劳动关系或争议合同期间。", "劳动合同" not in text, "补充招聘、工作安排、考勤和持续报酬证据。"),
        ("late_social_insurance", "社保开始较晚可能被解释为合作期或试用安排。", "social_insurance" not in fact_types, "核对实际入职、参保开始和用工管理材料。"),
    ]
    arguments = [
        {
            "scenario": scenario,
            "possible_argument": argument,
            "basis": basis,
            "currently_indicated": indicated,
            "certainty": "possibility_only",
            "fact_ids": [fact.id for fact in facts],
        }
        for scenario, argument, indicated, basis in rules
    ]
    return {"arguments": arguments, "invented_opponent_evidence": False, "confirmed_facts_only": True, "llm_used": False}
