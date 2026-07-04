# -*- coding: utf-8 -*-
"""
模块功能：印章区域提取与预处理服务
业务场景：从合同页面中裁剪检测到的印章区域，并进行去噪、增强、倾斜校正与尺寸归一化。
政策依据：无。
输入数据：原始页面图片、印章边界框。
输出结果：标准化印章子图的存储路径。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章提取服务
"""

from pathlib import Path
from typing import Any

import cv2
import numpy as np


# 默认印章子图输出目录
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "storage" / "seals"


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


def _crop_region(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """
    功能描述：按边界框安全裁剪图片区域。

    Args:
        image: 原始图片数组。
        bbox: (x1, y1, x2, y2)，可能越界。

    Returns:
        np.ndarray: 裁剪后的图片区域。
    """
    height, width = image.shape[:2]
    x1, y1, x2, y2 = bbox

    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))

    if x2 <= x1 or y2 <= y1:
        # 退化情况：返回 1x1 空白图，避免后续处理失败
        return np.zeros((1, 1, 3), dtype=np.uint8)

    return image[y1:y2, x1:x2]


def _denoise_and_enhance(image: np.ndarray) -> np.ndarray:
    """
    功能描述：对印章子图进行去噪、颜色增强与对比度增强。

    Args:
        image: 裁剪后的印章子图。

    Returns:
        np.ndarray: 增强后的子图。
    """
    # 双边滤波去噪，保留边缘
    denoised = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)

    # 转换到 LAB 颜色空间，对 L 通道做 CLAHE 增强
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_l = clahe.apply(l_channel)
    enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # 红色/蓝色通道轻微增强，提升印章文字与背景的对比度
    hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = cv2.multiply(s, np.full(s.shape, 1.1, dtype=np.float32))
    s = np.clip(s, 0, 255).astype(np.uint8)
    enhanced_hsv = cv2.merge([h, s, v])
    enhanced = cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)

    return enhanced


def _correct_skew(image: np.ndarray) -> np.ndarray:
    """
    功能描述：对印章子图进行轻微倾斜校正。

    业务逻辑：
        1. 检测印章主色区域；
        2. 计算区域最小外接矩形角度；
        3. 以图片中心为旋转中心进行旋转校正。

    Args:
        image: 增强后的印章子图。

    Returns:
        np.ndarray: 倾斜校正后的子图。
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

    # 红色
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255])))
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array([160, 80, 80]), np.array([180, 255, 255])))
    # 蓝色
    mask = cv2.bitwise_or(mask, cv2.inRange(hsv, np.array([100, 80, 80]), np.array([130, 255, 255])))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image

    largest_contour = max(contours, key=cv2.contourArea)
    if len(largest_contour) < 5:
        return image

    ellipse = cv2.fitEllipse(largest_contour)
    angle = ellipse[2]

    # 仅对明显倾斜进行校正
    if abs(angle) < 5 or abs(angle - 90) < 5:
        return image

    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rotation_matrix, (width, height), borderValue=(255, 255, 255))

    return rotated


def _normalize_size(image: np.ndarray, target_size: int = 256) -> np.ndarray:
    """
    功能描述：将印章子图归一化为目标尺寸，并保持宽高比填充白边。

    Args:
        image: 处理后的印章子图。
        target_size: 目标边长。

    Returns:
        np.ndarray: target_size x target_size 的标准化子图。
    """
    height, width = image.shape[:2]
    if height == 0 or width == 0:
        return np.full((target_size, target_size, 3), 255, dtype=np.uint8)

    # 保持宽高比缩放
    scale = target_size / max(height, width)
    new_width = int(width * scale)
    new_height = int(height * scale)
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # 居中填充到 target_size x target_size
    canvas = np.full((target_size, target_size, 3), 255, dtype=np.uint8)
    y_offset = (target_size - new_height) // 2
    x_offset = (target_size - new_width) // 2
    canvas[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = resized

    return canvas


def extract_seal_region(
    image_input: str | Path | np.ndarray,
    bbox: tuple[int, int, int, int],
    output_dir: str | Path | None = None,
    target_size: int = 256,
) -> Path:
    """
    功能描述：提取并预处理印章区域，保存为标准化的 PNG 子图。

    业务逻辑：
        1. 读取原始图片；
        2. 安全裁剪印章边界框；
        3. 去噪、对比度增强、颜色增强；
        4. 轻微倾斜校正；
        5. 尺寸归一化并保存。

    Args:
        image_input: 原始图片路径或 OpenCV 数组。
        bbox: 印章边界框 (x1, y1, x2, y2)。
        output_dir: 输出目录，默认 backend/app/storage/seals。
        target_size: 输出子图边长。

    Returns:
        Path: 保存的印章子图绝对路径。
    """
    image = _read_image(image_input)

    output_path = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    cropped = _crop_region(image, bbox)
    enhanced = _denoise_and_enhance(cropped)
    corrected = _correct_skew(enhanced)
    normalized = _normalize_size(corrected, target_size=target_size)

    # 使用 bbox 哈希生成唯一文件名，避免同一印章多次提取时文件名冲突
    x1, y1, x2, y2 = bbox
    filename = f"seal_{x1}_{y1}_{x2}_{y2}_{target_size}.png"
    target_file = output_path / filename

    cv2.imwrite(str(target_file), normalized)
    return target_file.resolve()
