"""Generate wholly fictional, clearly labelled demo evidence.

Run with the bundled workspace Python so document/PDF dependencies are stable.
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples" / "demo-case"


def set_cn_font(run, size: float, bold: bool = False, color: str = "17212B") -> None:
    run.font.name = "Microsoft YaHei"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def make_work_record() -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_height = Inches(11)
    section.page_width = Inches(8.5)
    section.top_margin = section.bottom_margin = Inches(1)
    section.left_margin = section.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    set_cn_font(p.add_run("工作成果记录（测试数据·完全虚构）"), 18, True, "173F5F")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    set_cn_font(p.add_run("用于 Labor Case Agent 端到端测试，不代表真实个人或单位"), 9, False, "667085")

    table = doc.add_table(rows=1, cols=3)
    table.autofit = False
    widths = [Inches(1.35), Inches(1.55), Inches(3.6)]
    for i, (text, width) in enumerate(zip(["月份", "成果类型", "记录"], widths)):
        table.columns[i].width = width
        cell = table.rows[0].cells[i]
        cell.width = width
        set_cn_font(cell.paragraphs[0].add_run(text), 10, True, "FFFFFF")
        cell._tc.get_or_add_tcPr().append(_shading("173F5F"))

    rows = [
        ("2024年7月", "运营", "按负责人安排整理艺人项目排期并每日汇报进度。"),
        ("2025年5月", "海报", "完成活动海报初稿、修改记录和交付文件。"),
        ("2026年2月", "内容", "继续更新网络内容；当月仅收到第三人转账1000元。"),
        ("2026年6月", "争议", "社保记录显示停止缴纳，未收到书面解除通知。"),
    ]
    for row_values in rows:
        row = table.add_row()
        for i, (text, width) in enumerate(zip(row_values, widths)):
            row.cells[i].width = width
            set_cn_font(row.cells[i].paragraphs[0].add_run(text), 10)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    set_cn_font(p.add_run("说明："), 10, True, "9A6700")
    set_cn_font(p.add_run("本记录仅证明测试流程可以处理 DOCX，不证明任何真实劳动关系。"), 10)
    doc.save(OUT / "work-record.docx")


def _shading(fill: str):
    from docx.oxml import OxmlElement

    node = OxmlElement("w:shd")
    node.set(qn("w:fill"), fill)
    return node


def make_social_insurance_pdf() -> None:
    registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
        textColor=HexColor("#173F5F"),
        alignment=TA_CENTER,
    )
    body = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
    )
    path = OUT / "social-insurance.pdf"
    pdf = SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm
    )
    story = [
        Paragraph("社会保险缴费记录（测试数据·完全虚构）", title),
        Spacer(1, 5 * mm),
        Paragraph("劳动者：测试用户甲　　单位：北京某某文化传媒有限公司（虚构）", body),
        Spacer(1, 3 * mm),
    ]
    data = [
        ["缴费月份", "养老", "医疗", "失业", "状态"],
        ["2025-06 至 2026-05", "已缴", "已缴", "已缴", "连续"],
        ["2026-06", "未缴", "未缴", "未缴", "停止"],
    ]
    table = Table(data, colWidths=[42 * mm, 25 * mm, 25 * mm, 25 * mm, 35 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#173F5F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D0D5DD")),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 5 * mm),
            Paragraph("备注：本文件为自动化测试样本，不是社保机构出具的真实证明。", body),
        ]
    )
    pdf.build(story)


def make_expected_results() -> None:
    expected = {
        "fixture": "wholly_fictional_test_data",
        "worker": "测试用户甲",
        "company": "北京某某文化传媒有限公司（虚构）",
        "salary_agreement": "6000.00",
        "employment_start_precision": "month",
        "employment_start": "2024-07",
        "social_insurance_start": "2025-06",
        "social_insurance_stop": "2026-06",
        "february_2026_expected": "6000.00",
        "february_2026_paid": "1000.00",
        "february_2026_arrears": "5000.00",
        "third_party_payment": True,
        "must_remain_unconfirmed": [
            "双方必然构成劳动关系",
            "公司在2026年6月违法解除",
            "无备注转账必然属于工资"
        ],
        "required_export_members": [
            "README-案件说明.md",
            "extracted/confirmed-facts.json",
            "extracted/timeline.json",
            "audit/export-manifest.json"
        ]
    }
    (OUT / "expected-results.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_work_record()
    make_social_insurance_pdf()
    make_expected_results()
    print(OUT)

