# -*- coding: utf-8 -*-
"""
模块功能：文件格式识别层
业务场景：识别上传文件的格式类型，判断是否需要OCR处理
政策依据：无（技术模块）
输入数据：文件路径
输出结果：FormatRecognitionResult（文件格式、置信度、是否需要OCR等）
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，支持PDF文字型/图片型、OFD、XML、Excel、CSV、图片等格式
"""

import logging
from pathlib import Path

from app.services.doc_parsing.parser_engine.parse_result import (
    FileFormat,
    FormatRecognitionResult,
    FILE_FORMAT_LABELS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 文件后缀与格式映射
# =============================================================================

# 文件后缀到格式的直接映射
SUFFIX_TO_FORMAT: dict[str, FileFormat] = {
    # PDF类
    ".pdf": FileFormat.PDF_TEXT,  # 先假设文字型，后续检测
    ".ofd": FileFormat.OFD,
    
    # Excel类
    ".xlsx": FileFormat.EXCEL,
    ".xls": FileFormat.EXCEL,
    
    # CSV类
    ".csv": FileFormat.CSV,
    
    # XML类
    ".xml": FileFormat.XML,
    
    # 图片类
    ".jpg": FileFormat.IMAGE,
    ".jpeg": FileFormat.IMAGE,
    ".png": FileFormat.IMAGE,
    ".bmp": FileFormat.IMAGE,
    ".tiff": FileFormat.IMAGE,
    ".tif": FileFormat.IMAGE,
    
    # 文档类
    ".txt": FileFormat.TEXT,
    ".doc": FileFormat.WORD,
    ".docx": FileFormat.WORD,
    ".md": FileFormat.MARKDOWN,
}

# 图片型PDF的特征阈值（提取文本字符数小于此值判定为图片型）
PDF_TEXT_THRESHOLD = 50


class FormatRecognizer:
    """
    文件格式识别器
    
    功能描述：识别文件格式，判断是否可处理，是否需要OCR
    业务逻辑：
        1. 根据文件后缀判断基本格式
        2. 对PDF文件进一步检测是否为文字型或图片型
        3. 判断是否可以直接提取文本，或需要OCR处理
    
    会计口径：无（技术模块）
    """
    
    def recognize(self, file_path: str) -> FormatRecognitionResult:
        """
        识别文件格式
        
        Args:
            file_path: 文件存储路径
            
        Returns:
            FormatRecognitionResult: 格式识别结果
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        # 1. 根据后缀判断基本格式
        base_format = SUFFIX_TO_FORMAT.get(suffix, FileFormat.UNKNOWN)
        
        if base_format == FileFormat.UNKNOWN:
            return FormatRecognitionResult(
                file_format=FileFormat.UNKNOWN,
                file_suffix=suffix,
                confidence=0.0,
                can_extract_text=False,
                needs_ocr=False,
                error_message=f"无法识别的文件格式：{suffix}",
            )
        
        # 2. 对PDF文件进一步检测
        if base_format == FileFormat.PDF_TEXT:
            actual_format, needs_ocr, confidence = self._detect_pdf_type(file_path)
            return FormatRecognitionResult(
                file_format=actual_format,
                file_suffix=suffix,
                confidence=confidence,
                can_extract_text=(actual_format == FileFormat.PDF_TEXT),
                needs_ocr=needs_ocr,
            )
        
        # 3. 其他格式直接返回
        can_extract_text = self._can_extract_text_directly(base_format)
        needs_ocr = base_format in {FileFormat.PDF_IMAGE, FileFormat.IMAGE}
        
        return FormatRecognitionResult(
            file_format=base_format,
            file_suffix=suffix,
            confidence=1.0,
            can_extract_text=can_extract_text,
            needs_ocr=needs_ocr,
        )
    
    def _detect_pdf_type(self, file_path: str) -> tuple[FileFormat, bool, float]:
        """
        检测PDF类型（文字型 vs 图片型）
        
        算法：
        1. 尝试使用pdfplumber提取文本
        2. 统计提取到的文本字符数
        3. 如果字符数 < 50，判定为图片型PDF
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            (FileFormat, needs_ocr, confidence)
        """
        try:
            import pdfplumber
            
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                # 只检查前3页，避免处理大文件耗时过长
                for page in pdf.pages[:3]:
                    page_text = page.extract_text() or ""
                    text_parts.append(page_text)
            
            total_text = "\n".join(text_parts)
            text_length = len(total_text.strip())
            
            # 判断是否为图片型PDF
            if text_length < PDF_TEXT_THRESHOLD:
                return FileFormat.PDF_IMAGE, True, 0.85
            else:
                return FileFormat.PDF_TEXT, False, 0.95
                
        except Exception as e:
            logger.warning(f"PDF类型检测失败 {file_path}: {e}")
            # 检测失败时，保守假设为图片型（需要OCR）
            return FileFormat.PDF_IMAGE, True, 0.5
    
    def _can_extract_text_directly(self, format_type: FileFormat) -> bool:
        """
        判断是否可以直接提取文本（不需要OCR）
        
        Args:
            format_type: 文件格式类型
            
        Returns:
            bool: 是否可以直接提取文本
        """
        directly_extractable = {
            FileFormat.PDF_TEXT,
            FileFormat.EXCEL,
            FileFormat.CSV,
            FileFormat.XML,
            FileFormat.TEXT,
            FileFormat.WORD,
            FileFormat.MARKDOWN,
            FileFormat.OFD,
        }
        return format_type in directly_extractable
    
    def get_format_label(self, format_type: FileFormat) -> str:
        """
        获取格式类型的中文标签
        
        Args:
            format_type: 文件格式类型
            
        Returns:
            str: 中文标签
        """
        return FILE_FORMAT_LABELS.get(format_type.value, "未知格式")


def recognize_file_format(file_path: str) -> FormatRecognitionResult:
    """
    便捷函数：识别文件格式
    
    Args:
        file_path: 文件存储路径
        
    Returns:
        FormatRecognitionResult: 格式识别结果
    """
    recognizer = FormatRecognizer()
    return recognizer.recognize(file_path)