import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ocr_reader = None


def _get_ocr_reader() -> Any | None:
    """获取 EasyOCR 阅读器（延迟加载）"""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
        except Exception as exc:
            logger.warning(f"EasyOCR 初始化失败: {exc}")
            _ocr_reader = None
    return _ocr_reader


def extract_text_from_image(path: str) -> str:
    """从图片中提取文字（支持 jpg/png/jpeg/bmp/tiff）"""
    reader = _get_ocr_reader()
    if reader is None:
        return ""
    
    try:
        results = reader.readtext(str(path), detail=0)
        return "\n".join(filter(None, results))
    except Exception as exc:
        logger.warning(f"OCR 提取失败 {path}: {exc}")
        return ""
