from __future__ import annotations

import shutil
import zipfile
from decimal import Decimal
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


UNKNOWN = "[请本人填写]"
SOURCE_ORG = "北京市朝阳区劳动人事争议仲裁委员会"
SOURCE_SCOPE = "根据用户提供的北京市朝阳区仲裁公开下载材料提炼字段结构，材料下载于2026年7月。"
LOCALITY_WARNING = "本文件为辅助预填版，不是仲裁机构制式原件；请以拟提交仲裁机构最新要求为准。"
SAFETY_NOTE = "正文仅使用用户已确认事实；未确认的机器提取内容不会进入本材料包。"


def _set_cell_shading(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shading = props.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        props.append(shading)
    shading.set(qn("w:fill"), fill)


def _set_cell_text(cell, text: str, bold: bool = False) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(10.5)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _base_document(title: str) -> Document:
    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    normal = document.styles["Normal"]
    normal.font.name = "宋体"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(10.5)

    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.space_after = Pt(8)
    run = heading.add_run(title)
    run.bold = True
    run.font.name = "黑体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    run.font.size = Pt(18)

    warning = document.add_paragraph()
    warning.paragraph_format.space_after = Pt(6)
    warning_run = warning.add_run(f"预填提示：{LOCALITY_WARNING}")
    warning_run.bold = True
    warning_run.font.color.rgb = RGBColor(0x9A, 0x34, 0x1E)
    return document


def _table(document: Document, rows: list[tuple[str, str]], widths=(4.0, 13.0)):
    table = document.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].width = Cm(widths[0])
        cells[1].width = Cm(widths[1])
        _set_cell_text(cells[0], label, bold=True)
        _set_cell_shading(cells[0], "E9EEF2")
        _set_cell_text(cells[1], value or UNKNOWN)
    return table


def _party(parties: list[models.Party], kinds: set[str]) -> models.Party | None:
    return next((party for party in parties if party.party_type in kinds), None)


def _party_name(party: models.Party | None) -> str:
    if not party:
        return UNKNOWN
    return party.company_name or party.name or UNKNOWN


def _claims_text(claims: list[models.Claim]) -> list[str]:
    if not claims:
        return [UNKNOWN]
    result = []
    for index, claim in enumerate(claims, 1):
        amount = f"：{format(Decimal(claim.amount), '.2f')}元" if claim.amount is not None else "（金额请本人填写）"
        result.append(f"{index}. {claim.title}{amount}")
    return result


def _confirmed_fact_lines(facts: list[models.ExtractedFact]) -> list[str]:
    if not facts:
        return [UNKNOWN]
    return [
        f"{index}. {fact.user_corrected_value or fact.normalized_value or fact.object_value}"
        for index, fact in enumerate(facts, 1)
    ]


def _add_lines(document: Document, heading: str, lines: list[str]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(heading)
    run.bold = True
    run.font.name = "黑体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    for line in lines:
        item = document.add_paragraph()
        item.paragraph_format.space_after = Pt(3)
        item.add_run(line)


def _application(
    path: Path,
    case: models.Case,
    worker: models.Party | None,
    company: models.Party | None,
    claims: list[models.Claim],
    facts: list[models.ExtractedFact],
) -> None:
    document = _base_document("劳动仲裁申请书（预填版）")
    _table(
        document,
        [
            ("申请人姓名", _party_name(worker)),
            ("性别/出生日期", UNKNOWN),
            ("身份证件号码", worker.identity_number_masked if worker and worker.identity_number_masked else UNKNOWN),
            ("住所/通讯地址", UNKNOWN),
            ("联系电话", UNKNOWN),
            ("被申请人名称", _party_name(company)),
            ("统一社会信用代码", company.unified_social_credit_code if company and company.unified_social_credit_code else UNKNOWN),
            ("注册地址/经营地址", UNKNOWN),
            ("法定代表人及职务", UNKNOWN),
            ("联系电话", UNKNOWN),
            ("拟申请仲裁地区", case.jurisdiction_region or UNKNOWN),
        ],
    )
    _add_lines(document, "仲裁请求", _claims_text(claims))
    _add_lines(document, "事实和理由（仅使用用户已确认事实）", _confirmed_fact_lines(facts))
    document.add_paragraph(SAFETY_NOTE)
    document.add_paragraph("申请人签名：____________________    日期：______年____月____日")
    document.add_paragraph("提交前请核对：请求是否明确、金额是否与欠薪明细一致、被申请人名称及地址是否来自最新工商登记。")
    document.save(path)


def _service_address(path: Path, worker: models.Party | None, company: models.Party | None) -> None:
    document = _base_document("当事人送达地址确认书（预填版）")
    _table(
        document,
        [
            ("申请人/接收文书人", _party_name(worker)),
            ("申请人送达地址", UNKNOWN),
            ("申请人联系电话", UNKNOWN),
            ("电子邮箱", UNKNOWN),
            ("拟选送达方式", "□短信  □电子邮件  □现场领取（请本人勾选）"),
            ("被申请人名称", _party_name(company)),
            ("被申请人送达地址", UNKNOWN),
            ("被申请人联系方式", UNKNOWN),
        ],
    )
    document.add_paragraph("本人确认上述地址和方式准确、有效；如有变更，将按受理机构要求及时书面告知。")
    document.add_paragraph("当事人签名：____________________    日期：______年____月____日")
    document.save(path)


def _evidence_catalog(path: Path, evidence: list[models.Evidence]) -> None:
    document = _base_document("证据材料清单（预填版）")
    document.add_paragraph("证据名称、证明目的、页数和原件情况必须由提交人复核；开庭时按通知携带原件。")
    table = document.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["编号", "证据材料名称", "证据种类", "有无原件", "证明对象及内容", "页数"]
    for cell, label in zip(table.rows[0].cells, headers):
        _set_cell_text(cell, label, bold=True)
        _set_cell_shading(cell, "DCE6F1")
    if not evidence:
        evidence_rows = [("EV-___", UNKNOWN, UNKNOWN, "□有 □无", UNKNOWN, UNKNOWN)]
    else:
        evidence_rows = [
            (
                item.evidence_number,
                item.original_filename,
                item.document_type or "其他",
                "□有 □无（请勾选）",
                item.source_description or UNKNOWN,
                str(item.page_count) if item.page_count else UNKNOWN,
            )
            for item in evidence
        ]
    for values in evidence_rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            _set_cell_text(cell, value)
    document.add_paragraph("提交人签字（盖章）：________________    提交日期：______年____月____日")
    document.save(path)


def _case_elements(path: Path, case: models.Case, wages: list[models.WageEntry]) -> None:
    document = _base_document("劳动争议案件审理要素表（预填版）")
    expected = sum((Decimal(item.expected_amount) for item in wages), Decimal("0"))
    paid = sum((Decimal(item.paid_amount) for item in wages), Decimal("0"))
    _table(
        document,
        [
            ("入职时间", case.employment_start_date.isoformat() if case.employment_start_date else UNKNOWN),
            ("岗位", UNKNOWN),
            ("是否缴纳社会保险", "□是 □否 □不清楚（请本人勾选）"),
            ("劳动合同", "□已签 □未签 □不清楚（请本人勾选）"),
            ("工资标准/构成", f"工资记录应付合计 {expected:.2f} 元；具体月标准和构成请本人核对" if wages else UNKNOWN),
            ("工资发放情况及周期", f"工资记录已付合计 {paid:.2f} 元；发薪日和方式请本人填写" if wages else UNKNOWN),
            ("正常工作至", case.employment_end_date.isoformat() if case.employment_end_date else UNKNOWN),
            ("劳动关系状态", "□已解除（终止） □未解除 □存在争议（请本人勾选）"),
            ("解除提出方及原因", UNKNOWN),
        ],
    )
    document.add_paragraph("本人承诺上述情况经本人核对属实。签名：________________    日期：______年____月____日")
    document.save(path)


def _checklist(path: Path, respondent_count: int) -> None:
    document = _base_document("线下立案与出庭材料核对清单")
    copies = "通常申请书一式四份；有共同被申请人时通常增加副本（本案被申请人数：%d）。" % respondent_count
    sections = [
        ("提交前", [
            "□ 先确认受案范围、仲裁管辖和仲裁时效；必要时向拟提交机构核实。",
            f"□ {copies}",
            "□ 申请书本人签名并填写真实日期；关键金额与欠薪明细逐项核对。",
            "□ 身份证明原件供核验，复印件使用A4纸。",
            "□ 准备送达地址确认书；地址、手机号和邮箱保持可用。",
        ]),
        ("证据交换/出庭", [
            "□ 证据和证据清单通常各准备两份；共同当事人或当地要求可能需要增加。",
            "□ 复印件按证据编号和页码排序，开庭携带原件。",
            "□ 视听资料通常准备两份拷贝和两份完整书面对话记录。",
            "□ 在通知规定的举证期限内提交；证人出庭按通知提前申请。",
            "□ 携带受理回执、开庭通知、身份证明及全部材料备份。",
        ]),
        ("重要提醒", [
            "□ 所有份数、送达方式、签章和截止日期，以拟提交仲裁机构最新要求为准。",
            "□ 本材料包不替代仲裁机构制式表格，不构成正式法律意见。",
        ]),
    ]
    for heading, lines in sections:
        _add_lines(document, heading, lines)
    document.save(path)


def create_filing_pack(db: Session, case: models.Case, exports_dir: Path) -> Path:
    parties = db.scalars(select(models.Party).where(models.Party.case_id == case.id)).all()
    worker = _party(parties, {"worker"})
    company = _party(parties, {"company"})
    respondents = [party for party in parties if party.party_type != "worker"]
    claims = db.scalars(select(models.Claim).where(models.Claim.case_id == case.id).order_by(models.Claim.id)).all()
    facts = db.scalars(
        select(models.ExtractedFact)
        .where(models.ExtractedFact.case_id == case.id, models.ExtractedFact.review_status == "user_confirmed")
        .order_by(models.ExtractedFact.confirmed_at, models.ExtractedFact.id)
    ).all()
    evidence = db.scalars(select(models.Evidence).where(models.Evidence.case_id == case.id).order_by(models.Evidence.evidence_number)).all()
    wages = db.scalars(select(models.WageEntry).where(models.WageEntry.case_id == case.id).order_by(models.WageEntry.period)).all()

    stage = (exports_dir / "offline-filing-pack").resolve()
    if exports_dir.resolve() not in stage.parents:
        raise ValueError("unsafe filing pack path")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    _application(stage / "01-劳动仲裁申请书-预填版.docx", case, worker, company, claims, facts)
    _service_address(stage / "02-送达地址确认书-预填版.docx", worker, company)
    _evidence_catalog(stage / "03-证据材料清单-预填版.docx", evidence)
    _case_elements(stage / "04-案件审理要素表-预填版.docx", case, wages)
    _checklist(stage / "05-线下办理核对清单.docx", len(respondents))
    (stage / "README-来源与适用范围.txt").write_text(
        "\n".join(
            [
                "劳动争议案件工作台 - 线下立案材料包",
                "",
                SOURCE_SCOPE,
                f"参考机构：{SOURCE_ORG}",
                "参考材料：申请仲裁提示、申请书模板、送达地址确认书、证据材料清单、案件审理要素表、仲裁立案流程提示。",
                "",
                LOCALITY_WARNING,
                SAFETY_NOTE,
                "本系统仅提供材料整理和文书预填，不构成正式法律意见。重要事实、金额、时效、管辖和最终提交内容必须由本人或专业人员复核。",
                "原始下载文件未被复制进本材料包。",
            ]
        ),
        encoding="utf-8",
    )

    output = exports_dir / "offline-filing-pack.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(stage.iterdir(), key=lambda item: item.name):
            archive.write(file, file.name)
    return output
