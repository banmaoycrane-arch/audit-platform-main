# -*- coding: utf-8 -*-
"""
模块功能：印章识别测试用例的合成图片生成工具。
业务场景：为印章检测、提取、OCR 服务提供可重复生成的测试样本。
政策依据：无。
输入数据：印章文本、图片尺寸、印章中心与半径。
输出结果：PNG 格式的合成印章图片路径。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建合成印章图片生成器
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FIXTURE_DIR = Path(__file__).resolve().parent


def _default_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    功能描述：尝试加载系统 TrueType 字体，失败则回退到 Pillow 默认位图字体。
    业务逻辑：优先使用 Arial/SimHei 等可缩放字体，确保不同环境下字号一致。
    """
    candidates = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_red_seal_image(
    output_name: str,
    seal_text: str,
    size: tuple[int, int] = (600, 400),
    center: tuple[int, int] | None = None,
    radius: int = 90,
    line_width: int = 4,
) -> Path:
    """
    功能描述：生成白色背景、红色圆形印章的合成测试图片。
    业务逻辑：先绘制红色圆环，再在环内按弧形排布文字，最后在中心绘制五角星与横排文字。
    会计口径：无。

    Args:
        output_name: 输出 PNG 文件名。
        seal_text: 环形文字内容（如"甲方科技有限公司合同专用章"）。
        size: 图片宽高。
        center: 印章中心坐标，默认图片中心。
        radius: 印章外圆半径。
        line_width: 圆环线宽。

    Returns:
        Path: 生成的图片绝对路径。
    """
    output_path = FIXTURE_DIR / output_name
    image = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(image)

    center = center or (size[0] // 2, size[1] // 2)
    outer_color = (200, 40, 40)
    inner_color = (210, 60, 60)

    # 绘制外圆环
    bounding_box = [
        center[0] - radius,
        center[1] - radius,
        center[0] + radius,
        center[1] + radius,
    ]
    draw.ellipse(bounding_box, outline=outer_color, width=line_width)

    # 绘制内细圆环，模拟真实印章的同心圆结构
    inner_radius = radius - 12
    inner_box = [
        center[0] - inner_radius,
        center[1] - inner_radius,
        center[0] + inner_radius,
        center[1] + inner_radius,
    ]
    draw.ellipse(inner_box, outline=inner_color, width=max(1, line_width // 2))

    # 弧形文字：围绕印章上边缘半圆排列
    font_arc = _default_font(18)
    angle_step = 180 / max(len(seal_text), 1)
    text_radius = radius - 22
    for index, char in enumerate(seal_text):
        # 从左侧 180 度到右侧 0 度分布
        angle_deg = 180 - index * angle_step
        angle_rad = angle_deg * 3.141592653589793 / 180
        x = center[0] + text_radius * __import__("math").cos(angle_rad)
        y = center[1] - text_radius * __import__("math").sin(angle_rad)
        draw.text((x, y), char, fill=outer_color, font=font_arc)

    # 中心绘制简化五角星
    star_size = 16
    star_points = []
    for i in range(10):
        angle_deg = i * 36 - 90
        angle_rad = angle_deg * 3.141592653589793 / 180
        length = star_size if i % 2 == 0 else star_size // 2
        star_points.append((
            center[0] + length * __import__("math").cos(angle_rad),
            center[1] + length * __import__("math").sin(angle_rad),
        ))
    draw.polygon(star_points, fill=outer_color)

    # 中心下方横排文字
    font_center = _default_font(16)
    center_text = "合同专用章"
    bbox = draw.textbbox((0, 0), center_text, font=font_center)
    text_width = bbox[2] - bbox[0]
    draw.text(
        (center[0] - text_width // 2, center[1] + star_size + 4),
        center_text,
        fill=outer_color,
        font=font_center,
    )

    image.save(output_path, "PNG")
    return output_path


def generate_blue_seal_image(
    output_name: str,
    seal_text: str,
    size: tuple[int, int] = (600, 400),
    center: tuple[int, int] | None = None,
    radius: int = 70,
) -> Path:
    """
    功能描述：生成蓝色椭圆财务章风格的合成测试图片。
    业务逻辑：绘制蓝色椭圆外框与内部横排文字，用于测试蓝色印章检测分支。
    """
    output_path = FIXTURE_DIR / output_name
    image = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(image)

    center = center or (size[0] // 2, size[1] // 2)
    blue_color = (40, 80, 180)

    # 绘制椭圆外框
    draw.ellipse(
        [
            center[0] - radius,
            center[1] - radius * 2 // 3,
            center[0] + radius,
            center[1] + radius * 2 // 3,
        ],
        outline=blue_color,
        width=4,
    )

    # 内部横排文字
    font = _default_font(20)
    bbox = draw.textbbox((0, 0), seal_text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        (center[0] - text_width // 2, center[1] - 10),
        seal_text,
        fill=blue_color,
        font=font,
    )

    image.save(output_path, "PNG")
    return output_path


def ensure_default_fixtures() -> list[Path]:
    """
    功能描述：确保默认测试图片已生成并返回路径列表。
    业务逻辑：生成红色圆形合同章与蓝色椭圆财务章各一张，便于测试复用。
    """
    return [
        generate_red_seal_image("red_seal_01.png", "甲方科技有限公司合同专用章"),
        generate_red_seal_image(
            "red_seal_02.png",
            "乙方信息服务有限公司合同专用章",
            size=(800, 600),
            center=(400, 300),
            radius=120,
        ),
    ]
