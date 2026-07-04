# -*- coding: utf-8 -*-
"""
模块功能：印章提取与预处理服务单元测试。
业务场景：验证印章裁剪、去噪、倾斜校正、尺寸归一化功能。
政策依据：无。
输入数据：合成印章测试图片。
输出结果：测试通过/失败状态。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章提取服务测试
"""
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.basic_data.seal_extraction_service import extract_seal_region
from app.services.basic_data.seal_detection_service import detect_seals
from tests.fixtures.seals import ensure_default_fixtures


@pytest.fixture(scope="module", autouse=True)
def fixture_images(tmp_path_factory):
    """模块级测试图片生成。"""
    return ensure_default_fixtures()


def test_extract_seal_region_creates_png_file(fixture_images, tmp_path):
    """提取后的印章子图应为存在的 PNG 文件。"""
    image_path = fixture_images[0]
    detections = detect_seals(str(image_path))
    assert detections

    output_path = extract_seal_region(
        str(image_path),
        detections[0].bbox,
        output_dir=str(tmp_path),
        target_size=256,
    )
    assert output_path.exists()
    assert output_path.suffix == ".png"


def test_extract_seal_region_normalizes_size(fixture_images, tmp_path):
    """输出子图尺寸应归一化为 target_size x target_size。"""
    image_path = fixture_images[0]
    detections = detect_seals(str(image_path))
    output_path = extract_seal_region(
        str(image_path),
        detections[0].bbox,
        output_dir=str(tmp_path),
        target_size=256,
    )
    image = cv2.imread(str(output_path))
    assert image.shape[0] == 256
    assert image.shape[1] == 256


def test_extract_seal_region_with_array_input(fixture_images, tmp_path):
    """支持传入 OpenCV 数组作为输入。"""
    image_path = fixture_images[0]
    image = cv2.imread(str(image_path))
    detections = detect_seals(image)
    output_path = extract_seal_region(
        image,
        detections[0].bbox,
        output_dir=str(tmp_path),
        target_size=128,
    )
    result = cv2.imread(str(output_path))
    assert result.shape == (128, 128, 3)


def test_extract_seal_region_creates_output_directory(tmp_path):
    """未存在的输出目录应被自动创建。"""
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    output_dir = tmp_path / "nested" / "seals"
    output_path = extract_seal_region(
        image,
        (100, 100, 200, 200),
        output_dir=str(output_dir),
        target_size=128,
    )
    assert output_dir.exists()
    assert output_path.exists()


def test_extract_seal_region_invalid_path_raises():
    """无效图片路径应抛出 ValueError。"""
    with pytest.raises(ValueError, match="无法读取图片"):
        extract_seal_region("/not/a/real/image.png", (0, 0, 10, 10))


def test_extract_seal_region_safe_boundary_clamp(fixture_images, tmp_path):
    """bbox 越界时应安全裁剪，不报错。"""
    image_path = fixture_images[0]
    image = cv2.imread(str(image_path))
    height, width = image.shape[:2]
    oversized_bbox = (-50, -50, width + 100, height + 100)
    output_path = extract_seal_region(
        image,
        oversized_bbox,
        output_dir=str(tmp_path),
        target_size=128,
    )
    assert output_path.exists()
