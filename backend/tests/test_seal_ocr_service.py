# -*- coding: utf-8 -*-
"""
模块功能：印章 OCR 服务单元测试。
业务场景：验证 EasyOCR 文字识别、坐标映射与环形排序。
政策依据：无。
输入数据：合成印章子图或数组。
输出结果：测试通过/失败状态。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章 OCR 服务测试
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.basic_data.seal_ocr_service import (
    SealTextItem,
    _sort_text_items_by_angle,
    recognize_seal_text,
    text_items_to_dict_list,
)


def test_sort_text_items_by_angle_orders_by_atan2():
    """按 atan2 角度排序，范围 [-pi, pi]，右侧偏下角度最小。"""
    items = [
        SealTextItem(text="左", x=0, y=10, width=10, height=10, confidence=0.9),
        SealTextItem(text="上", x=10, y=0, width=10, height=10, confidence=0.9),
        SealTextItem(text="右", x=20, y=10, width=10, height=10, confidence=0.9),
        SealTextItem(text="下", x=10, y=20, width=10, height=10, confidence=0.9),
    ]
    sorted_items = _sort_text_items_by_angle(items)
    texts = [item.text for item in sorted_items]
    # 中心 (15,15)：上(-2.82) < 右(-0.79) < 下(1.11) < 左(2.82)
    assert texts == ["上", "右", "下", "左"]


def test_recognize_seal_text_returns_empty_when_ocr_unavailable():
    """EasyOCR 初始化失败时应返回空结果。"""
    with patch("app.services.basic_data.seal_ocr_service._get_ocr_reader", return_value=None):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        result = recognize_seal_text(image)
        assert result.text_items == []
        assert result.recognized_text == ""


def test_recognize_seal_text_applies_offset_and_sorts():
    """OCR 结果应正确应用 offset 并排序。"""
    fake_reader = MagicMock()
    fake_reader.readtext.return_value = [
        ([(5, 5), (15, 5), (15, 15), (5, 15)], "甲", 0.85),
        ([(25, 5), (35, 5), (35, 15), (25, 15)], "乙", 0.80),
    ]

    with patch("app.services.basic_data.seal_ocr_service._get_ocr_reader", return_value=fake_reader):
        image = np.full((64, 64, 3), 255, dtype=np.uint8)
        result = recognize_seal_text(image, offset=(100, 50))

    assert len(result.text_items) == 2
    assert all(item.x >= 100 for item in result.text_items)
    assert all(item.y >= 50 for item in result.text_items)


def test_text_items_to_dict_list_serializes_fields():
    """序列化函数应保留关键字段。"""
    items = [
        SealTextItem(text="测", x=10, y=20, width=30, height=40, confidence=0.88),
    ]
    dict_list = text_items_to_dict_list(items)
    assert len(dict_list) == 1
    assert dict_list[0]["text"] == "测"
    assert dict_list[0]["x"] == 10
    assert dict_list[0]["confidence"] == 0.88


def test_recognize_seal_text_handles_ocr_exception():
    """OCR 异常时应返回空结果，不抛错。"""
    fake_reader = MagicMock()
    fake_reader.readtext.side_effect = RuntimeError("mock ocr error")

    with patch("app.services.basic_data.seal_ocr_service._get_ocr_reader", return_value=fake_reader):
        image = np.full((64, 64, 3), 255, dtype=np.uint8)
        result = recognize_seal_text(image)
        assert result.text_items == []
        assert result.recognized_text == ""
