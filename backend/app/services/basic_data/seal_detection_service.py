# -*- coding: utf-8 -*-
"""
模块功能：印章区域检测服务。
业务场景：对合同扫描页或 PDF 转换后的图片进行印章定位，支撑后续提取与 OCR。
政策依据：无。
输入数据：BGR 格式图片（OpenCV 读取）或图片路径。
输出结果：检测到的印章区域列表，包含 bbox、置信度、外形初判与检测方法。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建传统 CV 印章检测服务
"""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class SealDetectionResult:
    """印章检测结果数据结构。"""

    bbox: tuple[int, int, int, int]
    confidence: float
    seal_shape: str
    detection_method: str


def _load_image(image_input: str | Path | np.ndarray) -> np.ndarray:
    """
    功能描述：统一加载图片为 OpenCV BGR 数组。
    业务逻辑：路径/Path 用 cv2.imread 读取，ndarray 直接透传。
    """
    if isinstance(image_input, np.ndarray):
        return image_input
    image_path = Path(image_input)
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"无法读取图片: {image_path}")
    return image


def _color_mask_for_seal(image_bgr: np.ndarray) -> np.ndarray:
    """
    功能描述：基于 HSV 颜色空间提取红色与蓝色印章像素掩码。
    业务逻辑：红色在 HSV 中跨越 0/180 边界，需合并两段范围；蓝色取常规范围。
    """
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    # 红色印章：H 在 0-10 与 160-180 两段
    red_lower_1 = np.array([0, 40, 40])
    red_upper_1 = np.array([15, 255, 255])
    red_lower_2 = np.array([160, 40, 40])
    red_upper_2 = np.array([180, 255, 255])
    red_mask_1 = cv2.inRange(hsv, red_lower_1, red_upper_1)
    red_mask_2 = cv2.inRange(hsv, red_lower_2, red_upper_2)
    red_mask = cv2.bitwise_or(red_mask_1, red_mask_2)

    # 蓝色印章：H 在 90-130 之间
    blue_lower = np.array([90, 40, 40])
    blue_upper = np.array([130, 255, 255])
    blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

    return cv2.bitwise_or(red_mask, blue_mask)


def _shape_score(contour: np.ndarray) -> tuple[str, float]:
    """
    功能描述：根据轮廓拟合形状并给出外形判断与置信分。
    业务逻辑：先计算最小外接矩形宽高比，再拟合椭圆；圆形/椭圆/矩形/未知按置信度排序返回。
    """
    if len(contour) < 5:
        return "unknown", 0.3

    area = cv2.contourArea(contour)
    if area <= 0:
        return "unknown", 0.3

    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return "unknown", 0.3

    # 圆形度：接近 1 表示更像圆
    circularity = 4 * np.pi * area / (perimeter * perimeter)

    # 最小外接矩形
    x, y, width, height = cv2.boundingRect(contour)
    aspect_ratio = min(width, height) / max(width, height) if max(width, height) > 0 else 0

    # 椭圆拟合
    try:
        ellipse = cv2.fitEllipse(contour)
        major_axis = max(ellipse[1])
        minor_axis = min(ellipse[1])
        ellipse_ratio = minor_axis / major_axis if major_axis > 0 else 0
    except cv2.error:
        ellipse_ratio = 0

    # 综合判断
    if circularity > 0.75 and aspect_ratio > 0.8:
        return "circle", min(0.95, circularity + 0.1)
    if ellipse_ratio > 0.6:
        return "ellipse", min(0.9, 0.7 + ellipse_ratio * 0.2)
    if aspect_ratio > 0.5:
        return "rectangle", min(0.8, 0.6 + aspect_ratio * 0.2)

    return "unknown", 0.4


def _merge_overlapping_boxes(
    boxes: list[tuple[int, int, int, int]],
    overlap_threshold: float = 0.3,
) -> list[tuple[int, int, int, int]]:
    """
    功能描述：合并高度重叠的检测框，避免同一印章被多次报告。
    业务逻辑：采用贪心 IOU 合并策略，将被包含或高重叠的小框合并到最大框。
    """
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]), reverse=True)
    merged: list[tuple[int, int, int, int]] = []

    while boxes:
        current = boxes.pop(0)
        remaining: list[tuple[int, int, int, int]] = []
        for box in boxes:
            inter_x1 = max(current[0], box[0])
            inter_y1 = max(current[1], box[1])
            inter_x2 = min(current[2], box[2])
            inter_y2 = min(current[3], box[3])
            inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
            if inter_area <= 0:
                remaining.append(box)
                continue
            box_area = (box[2] - box[0]) * (box[3] - box[1])
            current_area = (current[2] - current[0]) * (current[3] - current[1])
            union_area = box_area + current_area - inter_area
            iou = inter_area / union_area if union_area > 0 else 0
            if iou >= overlap_threshold or inter_area >= box_area * 0.9:
                current = (
                    min(current[0], box[0]),
                    min(current[1], box[1]),
                    max(current[2], box[2]),
                    max(current[3], box[3]),
                )
            else:
                remaining.append(box)
        merged.append(current)
        boxes = remaining

    return merged


def detect_seals(
    image_input: str | Path | np.ndarray,
    min_area: int = 300,
    max_area_ratio: float = 0.8,
    detection_method: str = "hsv_contour",
) -> list[SealDetectionResult]:
    """
    功能描述：检测图片中的印章区域。
    业务逻辑：通过 HSV 颜色分割提取候选像素，经形态学闭运算连接断裂区域，
             再查找轮廓并拟合形状，最终合并重叠框返回标准化结果。

    Args:
        image_input: 图片路径或 OpenCV BGR 数组。
        min_area: 印章最小像素面积，过滤噪点。
        max_area_ratio: 相对图片面积的最大允许比例，防止把整页当印章。
        detection_method: 检测方法标记，默认传统 CV；可传入 paddleocr 作为 fallback 标记。

    Returns:
        list[SealDetectionResult]: 印章检测结果列表。

    注意事项：
        1. 当前 MVP 采用传统 CV，PaddleOCR fallback 仅通过 detection_method 字段预留标记。
        2. 输入图片建议分辨率不低于 600x400，过小印章可能漏检。
    """
    image = _load_image(image_input)
    image_height, image_width = image.shape[:2]
    max_area = image_width * image_height * max_area_ratio

    # 颜色分割获取印章候选掩码
    color_mask = _color_mask_for_seal(image)

    # 形态学闭运算：连接印章断裂边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 查找轮廓
    contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidate_boxes: list[tuple[int, int, int, int]] = []
    shape_scores: dict[tuple[int, int, int, int], tuple[str, float]] = {}

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        x, y, width, height = cv2.boundingRect(contour)
        # 过滤过扁或过窄的噪点区域
        if width < 20 or height < 20:
            continue

        box = (x, y, x + width, y + height)
        candidate_boxes.append(box)
        shape_scores[box] = _shape_score(contour)

    merged_boxes = _merge_overlapping_boxes(candidate_boxes)

    results: list[SealDetectionResult] = []
    for box in merged_boxes:
        shape, confidence = shape_scores.get(box, ("unknown", 0.5))
        # 根据色彩掩码内非零像素占比微调置信度
        x1, y1, x2, y2 = box
        roi_mask = color_mask[y1:y2, x1:x2]
        mask_ratio = float(np.count_nonzero(roi_mask)) / max(roi_mask.size, 1)
        adjusted_confidence = min(0.99, confidence * (0.5 + 0.5 * mask_ratio))

        results.append(SealDetectionResult(
            bbox=box,
            confidence=round(adjusted_confidence, 4),
            seal_shape=shape,
            detection_method=detection_method,
        ))

    return results
