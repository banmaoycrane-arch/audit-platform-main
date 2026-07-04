# -*- coding: utf-8 -*-
"""
模块功能：印章文字 OCR 识别与环形文字重组服务。
业务场景：对预处理后的印章子图识别文字，并按印章中心角度排序重组为完整字符串。
政策依据：无。
输入数据：印章子图路径或数组。
输出结果：文字项列表（含坐标、置信度）与重组后的完整字符串。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章 OCR 服务
"""
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.services.doc_parsing.ocr_service import _get_ocr_reader

logger = logging.getLogger(__name__)


@dataclass
class SealTextItem:
    """印章内单个识别文字项。"""

    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class SealOcrResult:
    """印章 OCR 识别结果。"""

    text_items: list[SealTextItem]
    recognized_text: str


def _read_image_array(image_input: str | Path | np.ndarray) -> np.ndarray:
    """
    功能描述：统一读取印章子图为 RGB 数组。
    业务逻辑：路径读取后转换为 RGB；数组若为 BGR 也转换为 RGB。
    """
    if isinstance(image_input, np.ndarray):
        image = image_input
    else:
        try:
            import cv2
            image_result = cv2.imread(str(image_input))
            if image_result is None:
                raise ValueError(f"无法读取图片: {image_input}")
            image = image_result
        except Exception as exc:
            raise ValueError(f"读取印章子图失败: {exc}") from exc

    if image.ndim == 2:
        image = np.stack([image, image, image], axis=-1)

    if image.shape[2] == 4:
        image = image[:, :, :3]

    # OpenCV 读入为 BGR，EasyOCR 需要 RGB
    try:
        import cv2
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    except Exception:
        pass

    return image


def _bbox_from_easyocr_points(points: list[tuple[float, float]]) -> tuple[int, int, int, int]:
    """
    功能描述：将 EasyOCR 返回的四边形点转换为水平包围框。
    业务逻辑：取四个顶点的最小/最大 x、y。
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x1 = int(min(xs))
    y1 = int(min(ys))
    x2 = int(max(xs))
    y2 = int(max(ys))
    return x1, y1, x2, y2


def _center_of_bbox(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    """计算包围框中心点。"""
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _sort_text_items_by_angle(text_items: list[SealTextItem]) -> list[SealTextItem]:
    """
    功能描述：按印章中心角度对文字项排序。
    业务逻辑：计算所有文字框的几何中心作为印章近似中心，再按 atan2 角度逆时针排序。
    """
    if not text_items:
        return []

    center_x = sum(item.x + item.width / 2 for item in text_items) / len(text_items)
    center_y = sum(item.y + item.height / 2 for item in text_items) / len(text_items)

    def angle_key(item: SealTextItem) -> float:
        mid_x = item.x + item.width / 2
        mid_y = item.y + item.height / 2
        return math.atan2(mid_y - center_y, mid_x - center_x)

    return sorted(text_items, key=angle_key)


def recognize_seal_text(
    image_input: str | Path | np.ndarray,
    offset: tuple[int, int] = (0, 0),
) -> SealOcrResult:
    """
    功能描述：识别印章子图中的文字，并返回带原始坐标的文字项。
    业务逻辑：复用现有 EasyOCR 阅读器；若初始化失败则返回空结果；
             文字坐标加上 offset 以映射回原始页面坐标系。

    Args:
        image_input: 印章子图路径或数组。
        offset: 子图在原始页面中的左上角偏移 (x, y)。

    Returns:
        SealOcrResult: 包含 text_items 与按角度重组后的 recognized_text。

    注意事项：
        1. 当前 MVP 优先复用 EasyOCR；PaddleOCR 作为后续扩展保留接口。
        2. 环形文字排序基于印章几何中心近似，倾斜严重或中心文字较多时可能偏差。
    """
    reader = _get_ocr_reader()
    if reader is None:
        logger.warning("EasyOCR 未初始化，返回空印章文字结果")
        return SealOcrResult(text_items=[], recognized_text="")

    image = _read_image_array(image_input)
    offset_x, offset_y = offset

    try:
        raw_results = reader.readtext(image)
    except Exception as exc:
        logger.warning(f"印章 OCR 识别失败: {exc}")
        return SealOcrResult(text_items=[], recognized_text="")

    text_items: list[SealTextItem] = []
    for result in raw_results:
        # EasyOCR 结果格式: (points, text, confidence)
        points, text, confidence = result
        x1, y1, x2, y2 = _bbox_from_easyocr_points(points)
        text_items.append(SealTextItem(
            text=str(text),
            x=x1 + offset_x,
            y=y1 + offset_y,
            width=x2 - x1,
            height=y2 - y1,
            confidence=float(confidence),
        ))

    sorted_items = _sort_text_items_by_angle(text_items)
    recognized_text = "".join(item.text for item in sorted_items)
    return SealOcrResult(text_items=sorted_items, recognized_text=recognized_text)


def text_items_to_dict_list(text_items: list[SealTextItem]) -> list[dict[str, Any]]:
    """
    功能描述：将 SealTextItem 列表序列化为可 JSON 存储的字典列表。
    """
    return [
        {
            "text": item.text,
            "x": item.x,
            "y": item.y,
            "width": item.width,
            "height": item.height,
            "confidence": round(item.confidence, 4),
        }
        for item in text_items
    ]
