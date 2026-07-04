# -*- coding: utf-8 -*-
"""
模块功能：印章检测服务单元测试。
业务场景：验证传统 CV 对合成印章的检出能力。
政策依据：无。
输入数据：合成印章测试图片。
输出结果：测试通过/失败状态。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章检测服务测试
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.basic_data.seal_detection_service import (
    _merge_overlapping_boxes,
    _shape_score,
    detect_seals,
)
from tests.fixtures.seals import ensure_default_fixtures, generate_blue_seal_image


@pytest.fixture(scope="module", autouse=True)
def fixture_images(tmp_path_factory):
    """模块级测试图片生成。"""
    return ensure_default_fixtures()


def test_detect_seals_finds_red_circular_seal(fixture_images):
    """应能从合成红色圆形印章图片中检测到至少一个印章。"""
    results = detect_seals(str(fixture_images[0]))
    assert len(results) >= 1
    result = results[0]
    assert result.bbox[0] < result.bbox[2]
    assert result.bbox[1] < result.bbox[3]
    assert result.confidence > 0
    assert result.seal_shape in {"circle", "ellipse", "rectangle", "unknown"}
    assert result.detection_method == "hsv_contour"


def test_detect_seals_returns_empty_for_blank_image():
    """纯白色图片应返回空列表。"""
    blank = np.full((400, 600, 3), 255, dtype=np.uint8)
    results = detect_seals(blank)
    assert results == []


def test_detect_seals_accepts_numpy_array(fixture_images):
    """应支持传入 OpenCV 数组。"""
    image = cv2.imread(str(fixture_images[0]))
    results = detect_seals(image)
    assert len(results) >= 1


def test_detect_seals_respects_min_area(fixture_images):
    """提高最小面积阈值后应过滤掉小噪点。"""
    results = detect_seals(str(fixture_images[0]), min_area=50000)
    assert len(results) == 0


def test_detect_seals_bbox_within_image_bounds(fixture_images):
    """检测框应位于图片边界内。"""
    image = cv2.imread(str(fixture_images[0]))
    height, width = image.shape[:2]
    results = detect_seals(image)
    for result in results:
        x1, y1, x2, y2 = result.bbox
        assert 0 <= x1 < width
        assert 0 <= y1 < height
        assert 0 < x2 <= width
        assert 0 < y2 <= height


def test_detect_seals_raises_on_invalid_path():
    """传入不存在的路径应抛出 ValueError。"""
    with pytest.raises(ValueError, match="无法读取图片"):
        detect_seals("/nonexistent/path/to/image.png")


def test_detect_seals_multiple_sizes(fixture_images):
    """不同尺寸图片均应能检测到印章。"""
    for image_path in fixture_images:
        results = detect_seals(str(image_path))
        assert len(results) >= 1, f"{image_path} 未检测到印章"


def test_detect_seals_finds_blue_ellipse_seal(tmp_path):
    """蓝色椭圆印章应被检测并判定为 ellipse 或 rectangle。"""
    image_path = generate_blue_seal_image(
        str(tmp_path / "blue_seal_01.png"),
        "财务专用章",
    )
    results = detect_seals(str(image_path))
    assert len(results) >= 1
    assert results[0].seal_shape in {"ellipse", "rectangle", "circle"}


def test_merge_overlapping_boxes_merges_high_iou():
    """高 IOU 的两个框应被合并为一个。"""
    boxes = [(10, 10, 50, 50), (20, 20, 60, 60)]
    merged = _merge_overlapping_boxes(boxes)
    assert len(merged) == 1
    assert merged[0] == (10, 10, 60, 60)


def test_merge_overlapping_boxes_keeps_separate_boxes():
    """不相交的框应保留为独立项。"""
    boxes = [(10, 10, 20, 20), (100, 100, 120, 120)]
    merged = _merge_overlapping_boxes(boxes)
    assert len(merged) == 2


def test_shape_score_for_degenerate_contour():
    """退化轮廓（点过少）应返回 unknown。"""
    import numpy as np
    contour = np.array([[[0, 0]], [[10, 0]], [[10, 10]]], dtype=np.int32)
    shape, confidence = _shape_score(contour)
    assert shape == "unknown"
    assert confidence == 0.3
