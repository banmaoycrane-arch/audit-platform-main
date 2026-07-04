# -*- coding: utf-8 -*-
"""
模块功能：印章区域检测服务
业务场景：基于传统计算机视觉（HSV 颜色分割 + 轮廓检测）定位合同扫描件中的印章区域。
政策依据：无。
输入数据：合同页面图片（文件路径或 OpenCV 数组）。
输出结果：印章边界框、置信度、外形初判及检测方法标记。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章检测服务
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass
class SealDetectionResult:
    """印章检测结果。"""

    bbox: tuple[int, int, int, int]
    confidence: float
    seal_shape: str
    detection_method: str


# HSV 颜色空间中红色印章的色相范围（红色在 HSV 中跨越 0°/180°，需取两段）
_RED_HSV_RANGES = [
    (np.array([0, 80, 80]), np.array([10, 255, 255])),
    (np.array([160, 80, 80]), np.array([180, 255, 255])),
]

# HSV 颜色空间中蓝色印章的色相范围
_BLUE_HSV_RANGE = (
    np.array([100, 80, 80]),
    np.array([130, 255, 255]),
)


def _read_image(image_input: str | Path | np.ndarray) -> np.ndarray:
    """
    功能描述：统一读取图片输入为 OpenCV BGR 数组。

    Args:
        image_input: 图片文件路径或 OpenCV 数组。

    Returns:
        np.ndarray: BGR 格式图片数组。

    Raises:
        ValueError: 无法读取图片时抛出。
    """
    if isinstance(image_input, np.ndarray):
        return image_input

    path = str(image_input)
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"无法读取图片：{path}")
    return image


def _segment_seal_color(image: np.ndarray) -> np.ndarray:
    """
    功能描述：在 HSV 颜色空间中分割红色与蓝色印章区域。

    Args:
        image: BGR 格式原图。

    Returns:
        np.ndarray: 二值掩码，印章候选区域为白色。
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

    # 红色印章（两段色相范围合并）
    for lower, upper in _RED_HSV_RANGES:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))

    # 蓝色印章
    blue_lower, blue_upper = _BLUE_HSV_RANGE
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, blue_lower, blue_upper))

    # 形态学闭运算连接断裂区域，开运算去除细小噪声
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    return mask


def _shape_score(contour: np.ndarray) -> tuple[str, float]:
    """
    功能描述：根据轮廓几何特征判断印章外形。

    Args:
        contour: OpenCV 轮廓点集。

    Returns:
        tuple[str, float]: 外形类别与置信度。
    """
    if len(contour) < 5:
        return "unknown", 0.3

    area = cv2.contourArea(contour)
    if area <= 0:
        return "unknown", 0.3

    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return "unknown", 0.3

    # 圆形度：4π*面积/周长²，越接近 1 越圆
    circularity = 4 * np.pi * area / (perimeter * perimeter)

    # 最小外接矩形宽高比
    x, y, width, height = cv2.boundingRect(contour)
    aspect_ratio = float(width) / max(height, 1)

    # 最小外接椭圆
    ellipse = cv2.fitEllipse(contour)
    major_axis = max(ellipse[1])
    minor_axis = min(ellipse[1])
    ellipse_ratio = minor_axis / max(major_axis, 1)

    if circularity > 0.75 and 0.9 <= aspect_ratio <= 1.1 and ellipse_ratio > 0.85:
        return "circle", min(0.95, circularity + 0.1)

    if 0.6 <= ellipse_ratio <= 0.95 or (0.5 <= aspect_ratio <= 2.0 and circularity > 0.5):
        return "ellipse", min(0.9, circularity + 0.05)

    return "rectangle", min(0.8, circularity + 0.05)


def _merge_overlapping_boxes(
    boxes: list[tuple[int, int, int, int]],
    overlap_threshold: float = 0.3,
) -> list[tuple[int, int, int, int]]:
    """
    功能描述：合并 IOU 超过阈值的边界框，避免同一印章被重复检测。

    Args:
        boxes: 边界框列表，格式 (x1, y1, x2, y2)。
        overlap_threshold: IOU 合并阈值。

    Returns:
        list[tuple[int, int, int, int]]: 合并后的边界框列表。
    """
    if not boxes:
        return []

    # 按面积从大到小排序，优先保留大框
    sorted_boxes = sorted(boxes, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]), reverse=True)
    merged: list[tuple[int, int, int, int]] = []

    for box in sorted_boxes:
        x1, y1, x2, y2 = box
        keep = True
        for idx, existing in enumerate(merged):
            ex1, ey1, ex2, ey2 = existing
            ix1, iy1 = max(x1, ex1), max(y1, ey1)
            ix2, iy2 = min(x2, ex2), min(y2, ey2)
            inter_width = max(0, ix2 - ix1)
            inter_height = max(0, iy2 - iy1)
            intersection = inter_width * inter_height
            union = (x2 - x1) * (y2 - y1) + (ex2 - ex1) * (ey2 - ey1) - intersection
            if union > 0 and intersection / union > overlap_threshold:
                # 合并为并集
                merged[idx] = (
                    min(x1, ex1),
                    min(y1, ey1),
                    max(x2, ex2),
                    max(y2, ey2),
                )
                keep = False
                break
        if keep:
            merged.append(box)

    return merged


def detect_seals(
    image_input: str | Path | np.ndarray,
    min_area: int = 300,
    max_area_ratio: float = 0.8,
    detection_method: str = "hsv_contour",
) -> list[SealDetectionResult]:
    """
    功能描述：检测图片中的印章区域。

    业务逻辑：
        1. HSV 颜色分割提取红色/蓝色印章候选区域；
        2. 形态学运算平滑掩码；
        3. 轮廓检测并过滤过小/过大区域；
        4. 拟合外形并计算置信度；
        5. 合并重叠框并返回结果。

    Args:
        image_input: 图片路径或 OpenCV 数组。
        min_area: 最小印章面积（像素），过滤噪点。
        max_area_ratio: 最大面积占图片比例，过滤整图误检。
        detection_method: 检测方法标识，默认 hsv_contour。

    Returns:
        list[SealDetectionResult]: 检测到的印章列表。
    """
    image = _read_image(image_input)
    height, width = image.shape[:2]
    image_area = height * width
    max_area = int(image_area * max_area_ratio)

    mask = _segment_seal_color(image)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidate_boxes: list[tuple[int, int, int, int]] = []
    candidate_scores: list[tuple[str, float]] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        x, y, box_width, box_height = cv2.boundingRect(contour)
        x1, y1 = x, y
        x2, y2 = x + box_width, y + box_height

        # 限制在图片边界内
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)

        if x2 <= x1 or y2 <= y1:
            continue

        shape, shape_confidence = _shape_score(contour)
        candidate_boxes.append((x1, y1, x2, y2))
        candidate_scores.append((shape, shape_confidence))

    merged_boxes = _merge_overlapping_boxes(candidate_boxes)

    results: list[SealDetectionResult] = []
    # 合并后按面积重新计算一次外形评分过于复杂，直接用 bounding box 对应的轮廓信息
    # 这里采用简化策略：按合并框覆盖区域内的掩码轮廓重新拟合
    for box in merged_boxes:
        x1, y1, x2, y2 = box
        roi_mask = mask[y1:y2, x1:x2]
        roi_contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not roi_contours:
            continue
        largest_contour = max(roi_contours, key=cv2.contourArea)
        shape, shape_confidence = _shape_score(largest_contour)

        # 检测置信度综合面积占比与外形置信度
        box_area = (x2 - x1) * (y2 - y1)
        area_ratio = box_area / image_area
        confidence = min(0.99, shape_confidence * (1 - area_ratio) + area_ratio * 0.5)

        results.append(
            SealDetectionResult(
                bbox=(x1, y1, x2, y2),
                confidence=round(confidence, 4),
                seal_shape=shape,
                detection_method=detection_method,
            )
        )

    return results
