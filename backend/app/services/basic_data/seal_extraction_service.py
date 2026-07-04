# -*- coding: utf-8 -*-
"""
模块功能：印章区域提取与预处理服务。
业务场景：将检测到的印章区域裁剪为标准化子图，便于 OCR 识别与人工复核。
政策依据：无。
输入数据：原始图片与检测框 bbox。
输出结果：裁剪、去噪、增强、归一化后的印章子图文件路径。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章提取与预处理服务
"""
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.core.config import BACKEND_DIR, get_settings


DEFAULT_OUTPUT_DIR = BACKEND_DIR / "app" / "storage" / "seals"


def _resolve_output_dir(output_dir: str | Path | None) -> Path:
    """
    功能描述：解析印章子图存储目录。
    业务逻辑：未指定时使用 backend/app/storage/seals；相对路径以 BACKEND_DIR 为根。
    """
    if output_dir is None:
        return DEFAULT_OUTPUT_DIR
    path = Path(output_dir)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path


def _crop_region(image_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """
    功能描述：按 bbox 裁剪原始图片中的印章区域。
    业务逻辑：校验边界并做安全裁剪，防止越界。
    """
    x1, y1, x2, y2 = bbox
    height, width = image_bgr.shape[:2]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(width, x2)
    y2 = min(height, y2)
    if x2 <= x1 or y2 <= y1:
        return image_bgr
    return image_bgr[y1:y2, x1:x2]


def _denoise_and_enhance(image_bgr: np.ndarray) -> np.ndarray:
    """
    功能描述：对印章子图进行去噪与颜色通道增强。
    业务逻辑：轻微双边滤波保留边缘，红色/蓝色通道通过 CLAHE 增强对比度。
    """
    # 双边滤波去噪，保持边缘清晰
    denoised = cv2.bilateralFilter(image_bgr, d=5, sigmaColor=50, sigmaSpace=50)

    # 转换到 LAB 空间，对亮度通道做自适应直方图均衡
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_l = clahe.apply(l_channel)
    enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # 轻微提升饱和度，使印章颜色更鲜明
    hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.int16) + 15, 0, 255).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _correct_skew(image_bgr: np.ndarray) -> np.ndarray:
    """
    功能描述：对轻微倾斜的印章子图进行透视校正。
    业务逻辑：基于颜色掩码查找最大轮廓，拟合最小外接矩形并旋转至水平。
    """
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    red_lower_1 = np.array([0, 40, 40])
    red_upper_1 = np.array([15, 255, 255])
    red_lower_2 = np.array([160, 40, 40])
    red_upper_2 = np.array([180, 255, 255])
    red_mask_1 = cv2.inRange(hsv, red_lower_1, red_upper_1)
    red_mask_2 = cv2.inRange(hsv, red_lower_2, red_upper_2)
    red_mask = cv2.bitwise_or(red_mask_1, red_mask_2)

    blue_lower = np.array([90, 40, 40])
    blue_upper = np.array([130, 255, 255])
    blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

    mask = cv2.bitwise_or(red_mask, blue_mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image_bgr

    largest = max(contours, key=cv2.contourArea)
    if len(largest) < 5:
        return image_bgr

    # 最小外接矩形，获取旋转角度
    rect = cv2.minAreaRect(largest)
    angle = rect[2]
    if angle < -45:
        angle += 90

    # 角度较小时直接旋转
    if abs(angle) < 5:
        center = (image_bgr.shape[1] // 2, image_bgr.shape[0] // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, scale=1.0)
        rotated = cv2.warpAffine(
            image_bgr,
            rotation_matrix,
            (image_bgr.shape[1], image_bgr.shape[0]),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        )
        return rotated

    return image_bgr


def _normalize_size(image_bgr: np.ndarray, target_size: int = 256) -> np.ndarray:
    """
    功能描述：将印章子图缩放到统一大小，便于模型输入与展示。
    业务逻辑：等比例缩放，短边补白至 target_size x target_size。
    """
    height, width = image_bgr.shape[:2]
    scale = target_size / max(height, width)
    new_width = int(width * scale)
    new_height = int(height * scale)
    resized = cv2.resize(image_bgr, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # 创建白色背景画布并居中放置
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
    功能描述：从原始图片中提取印章区域并输出标准化子图。
    业务逻辑：裁剪 → 去噪增强 → 轻微倾斜校正 → 尺寸归一化 → 保存 PNG。

    Args:
        image_input: 原始图片路径或 OpenCV BGR 数组。
        bbox: 印章区域 (x1, y1, x2, y2) 像素坐标。
        output_dir: 子图保存目录，默认 backend/app/storage/seals。
        target_size: 归一化画布尺寸。

    Returns:
        Path: 保存后的子图绝对路径。

    注意事项：
        1. 输出文件名使用 UUID，避免原文件名泄露。
        2. 子图以 PNG 保存，避免压缩导致印章边缘模糊。
    """
    if isinstance(image_input, np.ndarray):
        image = image_input
    else:
        image_result = cv2.imread(str(image_input))
        if image_result is None:
            raise ValueError(f"无法读取图片: {image_input}")
        image = image_result

    cropped = _crop_region(image, bbox)
    enhanced = _denoise_and_enhance(cropped)
    corrected = _correct_skew(enhanced)
    normalized = _normalize_size(corrected, target_size=target_size)

    output_path = _resolve_output_dir(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid4().hex}.png"
    target_file = output_path / file_name
    cv2.imwrite(str(target_file), normalized)
    return target_file
