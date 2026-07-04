# -*- coding: utf-8 -*-
"""
模块功能：解析修正回流服务
业务场景：处理人工复核修正，提取规则补丁，进行回归验证，实现系统自愈能力
政策依据：审计追踪要求、机器学习反馈闭环最佳实践
输入数据：修正记录、原始文本、解析结果
输出结果：规则补丁、回归验证报告、解析稳定性提升
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，实现修正记录、规则提取、回归验证核心功能
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.parse_correction import ParseCorrection, ParsingRulePatch

logger = logging.getLogger(__name__)


# =============================================================================
# 修正记录管理
# =============================================================================

def create_correction_record(
    db: Session,
    task_id: str,
    document_type: str,
    file_name: str,
    original_result: dict[str, Any],
    corrected_result: dict[str, Any],
    correction_reason: str = "",
    corrected_by: str = "",
) -> ParseCorrection:
    """
    创建修正记录
    
    功能描述：记录人工复核对解析结果的修正
    业务逻辑：
        1. 计算原始结果和修正结果的差异字段
        2. 创建修正记录并保存到数据库
        3. 记录修正原因和修正人
    
    Args:
        db: 数据库会话
        task_id: 解析任务ID
        document_type: 文档类型
        file_name: 原始文件名
        original_result: 原始解析结果
        corrected_result: 修正后的结果
        correction_reason: 修正原因
        corrected_by: 修正人
        
    Returns:
        ParseCorrection: 创建的修正记录
    """
    diff_fields = _calculate_diff_fields(original_result, corrected_result)
    
    record = ParseCorrection(
        task_id=task_id,
        document_type=document_type,
        file_name=file_name,
        original_result=original_result,
        corrected_result=corrected_result,
        diff_fields=diff_fields,
        correction_reason=correction_reason,
        corrected_by=corrected_by,
        status="pending",
        rule_extracted=False,
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    
    logger.info(f"创建修正记录 {record.id}：{document_type} - {file_name}，差异字段：{diff_fields}")
    return record


def _calculate_diff_fields(
    original: dict[str, Any],
    corrected: dict[str, Any],
) -> list[str]:
    """计算两个字典之间的差异字段列表。"""
    diff_fields = []
    
    all_keys = set(original.keys()) | set(corrected.keys())
    
    for key in all_keys:
        orig_val = original.get(key)
        corr_val = corrected.get(key)
        
        if orig_val != corr_val:
            diff_fields.append(key)
    
    return sorted(diff_fields)


def get_pending_corrections(
    db: Session,
    document_type: str = None,
    limit: int = 100,
) -> List[ParseCorrection]:
    """
    获取待处理的修正记录
    
    Args:
        db: 数据库会话
        document_type: 文档类型过滤（可选）
        limit: 返回数量限制
        
    Returns:
        List[ParseCorrection]: 待处理的修正记录列表
    """
    query = db.query(ParseCorrection).filter(
        ParseCorrection.status == "pending"
    )
    
    if document_type:
        query = query.filter(ParseCorrection.document_type == document_type)
    
    return query.order_by(ParseCorrection.created_at.desc()).limit(limit).all()


def get_correction_by_id(db: Session, correction_id: int) -> Optional[ParseCorrection]:
    """根据ID获取修正记录。"""
    return db.query(ParseCorrection).filter(ParseCorrection.id == correction_id).first()


# =============================================================================
# 规则提取引擎
# =============================================================================

def extract_rules_from_correction(
    db: Session,
    correction_id: int,
    original_text: str = "",
) -> List[ParsingRulePatch]:
    """
    从修正记录中提取规则补丁
    
    功能描述：分析修正差异，自动提取正则表达式或模板规则
    业务逻辑：
        1. 获取修正记录
        2. 分析每个差异字段的修正内容
        3. 尝试生成正则表达式或字段映射规则
        4. 创建规则补丁记录
        5. 更新修正记录状态为已分析
    
    Args:
        db: 数据库会话
        correction_id: 修正记录ID
        original_text: 原始文本内容（用于生成正则表达式）
        
    Returns:
        List[ParsingRulePatch]: 提取的规则补丁列表
    """
    correction = get_correction_by_id(db, correction_id)
    if not correction:
        logger.warning(f"修正记录不存在：{correction_id}")
        return []
    
    patches = []
    
    for field in correction.diff_fields:
        original_val = correction.original_result.get(field)
        corrected_val = correction.corrected_result.get(field)
        
        if corrected_val is None or corrected_val == "":
            continue
        
        patch = _generate_rule_patch(
            document_type=correction.document_type,
            field=field,
            original_val=original_val,
            corrected_val=corrected_val,
            original_text=original_text,
            source_correction_id=correction_id,
        )
        
        if patch:
            db.add(patch)
            patches.append(patch)
    
    if patches:
        db.commit()
        
        correction.rule_extracted = True
        correction.extracted_rule = {
            "patches": [p.rule_name for p in patches],
            "field_count": len(patches),
        }
        correction.status = "analyzed"
        db.commit()
        
        logger.info(f"从修正记录 {correction_id} 提取 {len(patches)} 条规则补丁")
    
    return patches


def _generate_rule_patch(
    document_type: str,
    field: str,
    original_val: Any,
    corrected_val: Any,
    original_text: str,
    source_correction_id: int,
) -> Optional[ParsingRulePatch]:
    """
    生成规则补丁
    
    业务逻辑：
        1. 如果有原始文本，尝试生成正则表达式规则
        2. 如果是字段值修正，尝试生成字段映射规则
        3. 如果是数值修正，尝试生成数值转换规则
    """
    rule_name = f"{document_type}_{field}_{int(datetime.now().timestamp())}"
    
    if original_text and corrected_val and isinstance(corrected_val, str):
        regex_pattern = _generate_regex_pattern(original_text, corrected_val)
        if regex_pattern:
            return ParsingRulePatch(
                rule_name=rule_name,
                document_type=document_type,
                rule_type="regex",
                rule_pattern=regex_pattern,
                target_field=field,
                priority=40,
                confidence_boost=5,
                status="draft",
                source_correction_id=source_correction_id,
            )
    
    if original_val and corrected_val and isinstance(original_val, str) and isinstance(corrected_val, str):
        if len(original_val) > 0 and len(corrected_val) > 0:
            mapping_pattern = _generate_mapping_rule(original_val, corrected_val)
            if mapping_pattern:
                return ParsingRulePatch(
                    rule_name=rule_name,
                    document_type=document_type,
                    rule_type="mapping",
                    rule_pattern=mapping_pattern,
                    target_field=field,
                    priority=35,
                    confidence_boost=8,
                    status="draft",
                    source_correction_id=source_correction_id,
                )
    
    return None


def _generate_regex_pattern(text: str, target_value: str) -> Optional[str]:
    """
    根据原始文本和目标值生成正则表达式
    
    业务逻辑：
        1. 在文本中查找目标值的上下文
        2. 提取目标值前后的固定文本作为正则表达式的边界
        3. 生成通用的正则表达式模式
    """
    if not text or not target_value:
        return None
    
    target_value = target_value.strip()
    if len(target_value) < 2:
        return None
    
    target_len = len(target_value)
    text_len = len(text)
    
    start_idx = text.find(target_value)
    if start_idx == -1:
        return None
    
    end_idx = start_idx + target_len
    
    prefix_len = min(20, start_idx)
    suffix_len = min(20, text_len - end_idx)
    
    prefix = text[start_idx - prefix_len:start_idx]
    suffix = text[end_idx:end_idx + suffix_len]
    
    prefix_pattern = re.escape(prefix) if prefix else ""
    suffix_pattern = re.escape(suffix) if suffix else ""
    
    value_pattern = _escape_for_regex(target_value)
    
    regex_pattern = ""
    if prefix_pattern:
        regex_pattern += prefix_pattern
    
    regex_pattern += r"\s*" + value_pattern + r"\s*"
    
    if suffix_pattern:
        regex_pattern += suffix_pattern
    
    if len(regex_pattern) > 500:
        return None
    
    try:
        re.compile(regex_pattern)
        return regex_pattern
    except re.error:
        return None


def _escape_for_regex(value: str) -> str:
    """转义特殊字符，但保留数字和日期模式。"""
    escaped = re.escape(value)
    
    escaped = escaped.replace(r"\d", "d")
    escaped = re.sub(r"\\d+", r"\\d+", escaped)
    escaped = escaped.replace("d", r"\d")
    
    escaped = re.sub(r"(\\d{4})[-/](\\d{2})[-/](\\d{2})", r"\1[-/]\2[-/]\3", escaped)
    
    return escaped


def _generate_mapping_rule(original_val: str, corrected_val: str) -> str:
    """生成字段映射规则。"""
    return json.dumps({
        "original": original_val,
        "corrected": corrected_val,
        "match_type": "exact" if len(original_val) > 10 else "fuzzy",
    }, ensure_ascii=False)


import json


# =============================================================================
# 回归验证
# =============================================================================

def run_regression_test(
    db: Session,
    patch_id: int,
    test_documents: List[Tuple[str, str, dict]],
) -> bool:
    """
    运行回归验证
    
    功能描述：使用历史文档测试新规则补丁是否破坏现有解析结果
    业务逻辑：
        1. 获取规则补丁
        2. 对测试文档应用新规则
        3. 检查是否产生新的错误或破坏原有正确结果
        4. 更新验证状态和日志
    
    Args:
        db: 数据库会话
        patch_id: 规则补丁ID
        test_documents: 测试文档列表，格式为 (document_type, text, expected_result)
        
    Returns:
        bool: 回归验证是否通过
    """
    patch = db.query(ParsingRulePatch).filter(ParsingRulePatch.id == patch_id).first()
    if not patch:
        logger.warning(f"规则补丁不存在：{patch_id}")
        return False
    
    passed = True
    log_lines = []
    
    for doc_type, text, expected in test_documents:
        if doc_type != patch.document_type:
            continue
        
        try:
            result = _apply_patch_to_text(patch, text)
            
            expected_val = expected.get(patch.target_field)
            actual_val = result.get(patch.target_field)
            
            if expected_val is not None and actual_val != expected_val:
                log_lines.append(f"FAIL: 字段 {patch.target_field} 预期 '{expected_val}'，实际 '{actual_val}'")
                passed = False
            else:
                log_lines.append(f"PASS: 字段 {patch.target_field} = '{actual_val}'")
        
        except Exception as e:
            log_lines.append(f"ERROR: {e}")
            passed = False
    
    patch.status = "active" if passed else "draft"
    
    correction_id = patch.source_correction_id
    if correction_id:
        correction = get_correction_by_id(db, correction_id)
        if correction:
            correction.regression_passed = 1 if passed else -1
            correction.regression_log = "\n".join(log_lines)
            correction.status = "applied" if passed else "analyzed"
    
    db.commit()
    
    logger.info(f"回归验证 {'通过' if passed else '失败'}：规则补丁 {patch_id}")
    return passed


def _apply_patch_to_text(patch: ParsingRulePatch, text: str) -> dict[str, Any]:
    """应用规则补丁到文本并返回结果。"""
    result = {}
    
    if patch.rule_type == "regex":
        match = re.search(patch.rule_pattern, text)
        if match:
            result[patch.target_field] = match.group(0).strip()
    
    elif patch.rule_type == "mapping":
        try:
            mapping = json.loads(patch.rule_pattern)
            if mapping.get("match_type") == "exact":
                if mapping.get("original") in text:
                    result[patch.target_field] = mapping.get("corrected")
        except json.JSONDecodeError:
            pass
    
    return result


# =============================================================================
# 动态规则加载
# =============================================================================

def get_active_rules_by_document_type(
    db: Session,
    document_type: str,
) -> List[ParsingRulePatch]:
    """
    获取指定文档类型的所有生效规则补丁
    
    功能描述：在规则引擎解析时，动态加载已通过回归验证的规则补丁
    业务逻辑：
        1. 查询状态为active的规则补丁
        2. 按优先级排序
        3. 返回规则列表
    
    Args:
        db: 数据库会话
        document_type: 文档类型
        
    Returns:
        List[ParsingRulePatch]: 生效的规则补丁列表（按优先级排序）
    """
    return db.query(ParsingRulePatch).filter(
        ParsingRulePatch.document_type == document_type,
        ParsingRulePatch.status == "active",
    ).order_by(ParsingRulePatch.priority).all()


def apply_dynamic_rules(
    db: Session,
    document_type: str,
    parsed_data: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    """
    应用动态规则补丁到解析结果
    
    功能描述：在规则引擎解析完成后，应用已生效的规则补丁进行补充或修正
    业务逻辑：
        1. 获取该文档类型的所有生效规则
        2. 按优先级依次应用规则
        3. 对于未提取的字段，尝试用动态规则提取
        4. 更新应用次数和成功率统计
    
    Args:
        db: 数据库会话
        document_type: 文档类型
        parsed_data: 原始解析结果
        text: 原始文本
        
    Returns:
        dict[str, Any]: 应用规则补丁后的解析结果
    """
    rules = get_active_rules_by_document_type(db, document_type)
    
    for rule in rules:
        field = rule.target_field
        
        if parsed_data.get(field) is None or parsed_data.get(field) == "":
            result = _apply_patch_to_text(rule, text)
            if result.get(field):
                parsed_data[field] = result[field]
                rule.applied_count += 1
                rule.success_rate = min(100, rule.success_rate + 2)
                logger.debug(f"应用规则补丁 {rule.id}：{field} = {result[field]}")
    
    db.commit()
    return parsed_data