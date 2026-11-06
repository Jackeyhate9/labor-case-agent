import pytest

from app.providers.ocr import _parse_unlimited_output


@pytest.mark.parametrize(
    ("payload", "width", "height", "expected_text", "expected_box", "expected_kind"),
    [
        ("<|det|>text [0, 0, 1000, 1000]<|/det|>全部", 2000, 1000, "全部", (0.0, 0.0, 2000.0, 1000.0), "text"),
        ("<|det|>title [250,250,750,750]<|/det|>标题", 800, 600, "标题", (200.0, 150.0, 400.0, 300.0), "title"),
        ("<|det|>table [900,900,1200,1300]<|/det|>边界", 100, 200, "边界", (90.0, 180.0, 10.0, 20.0), "table"),
        ("<|det|> [10,20,30,40]<|/det|>默认类型", 1000, 1000, "默认类型", (10.0, 20.0, 20.0, 20.0), "text"),
    ],
)
def test_unlimited_detection_parser_scales_and_clamps_native_coordinates(payload, width, height, expected_text, expected_box, expected_kind):
    text, regions = _parse_unlimited_output(payload, width, height)
    assert text == expected_text and len(regions) == 1
    region = regions[0]
    assert (region.bbox_x, region.bbox_y, region.bbox_width, region.bbox_height) == expected_box
    assert region.region_type == expected_kind


def test_unlimited_detection_parser_preserves_plain_text_without_markers():
    text, regions = _parse_unlimited_output("  模型纯文本结果  ", 1920, 1080)
    assert text == "模型纯文本结果"
    assert regions == []


def test_unlimited_detection_parser_ignores_empty_detection_text():
    payload = "<|det|>text [0,0,100,100]<|/det|>   "
    text, regions = _parse_unlimited_output(payload, 1000, 1000)
    assert text == payload.strip()
    assert regions == []
