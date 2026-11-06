from pathlib import Path

import pytest

from app.services import parse_document


DEMO = Path(__file__).resolve().parents[3] / "samples" / "demo-case"


@pytest.mark.parametrize(
    ("filename", "required_tokens"),
    [
        ("chat-01.png", ("测试数据", "6000", "2024年7月")),
        ("chat-02.png", ("测试数据", "1000", "2026年6月", "社保")),
    ],
)
def test_demo_chinese_screenshots_run_through_real_rapidocr(filename, required_tokens):
    pytest.importorskip("rapidocr_onnxruntime")

    pages, engine, warning = parse_document(DEMO / filename)

    assert engine == "rapidocr"
    assert warning is None
    assert len(pages) == 1
    for token in required_tokens:
        assert token in pages[0]
