"""系统运维负债扫描服务。

覆盖 6 大类问题：
1. 缺失健康检查端点（health_check）：容器编排/k8s 必需
2. 缺失速率限制（rate_limit）：API 无防滥用保护
3. 裸 except 块（bare_except）：except Exception 无结构化日志
4. 缺失日志覆盖（missing_logger）：服务模块无 logger
5. 缺失数据库索引（missing_index）：高频查询列无显式索引
6. N+1 查询风险（n_plus_one）：for 循环内嵌查询模式

扫描结果以结构化 dict 返回：{category_name: [{rule_id, name, count, severity}]}
"""
from __future__ import annotations

import ast
import importlib
import inspect
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# 扫描的根目录
APP_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class OpsFinding:
    rule_id: str
    name: str
    category: str
    severity: str
    count: int
    file_paths: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category,
            "severity": self.severity,
            "count": self.count,
            "file_paths": self.file_paths[:10],  # 最多 10 个
            "description": self.description,
        }


@dataclass
class OpsReport:
    generated_at: datetime
    findings: list[OpsFinding] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        by_cat: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        for f in self.findings:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        return {
            "categories": by_cat,
            "by_severity": by_sev,
            "finding_items": len(self.findings),
            "affected_files": len(set(p for f in self.findings for p in f.file_paths)),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary(),
            "findings": [f.to_dict() for f in self.findings],
        }


def _py_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _append(
    findings: list[OpsFinding],
    /,
    rule_id: str,
    name: str,
    category: str,
    severity: str,
    count: int,
    file_paths: list[str] | None = None,
    description: str = "",
) -> None:
    if count <= 0:
        return
    findings.append(OpsFinding(
        rule_id=rule_id,
        name=name,
        category=category,
        severity=severity,
        count=count,
        file_paths=file_paths or [],
        description=description,
    ))


# ======================== 1. 缺失健康检查端点 ========================

def _scan_health_check(findings: list[OpsFinding]) -> None:
    """检查是否存在 /health 端点。"""
    has_health = False
    health_files: list[str] = []
    for py_file in _py_files(APP_ROOT / "api"):
        content = py_file.read_text(encoding="utf-8")
        if "/health" in content or "health_check" in content.lower():
            has_health = True
            health_files.append(str(py_file.relative_to(APP_ROOT)))

    if not has_health:
        _append(
            findings,
            rule_id="ops_no_health_endpoint",
            name="缺失 /health 健康检查端点",
            category="health_check",
            severity=SEVERITY_CRITICAL,
            count=1,
            description="容器编排（k8s/Docker）需要 /health 端点做存活探针和就绪探针",
        )
    else:
        _append(
            findings,
            rule_id="ops_health_endpoint_present",
            name="存在健康检查端点",
            category="health_check",
            severity=SEVERITY_LOW,
            count=1,
            file_paths=health_files,
            description="已发现健康检查端点",
        )


# ======================== 2. 缺失速率限制 ========================

def _scan_rate_limit(findings: list[OpsFinding]) -> None:
    """检查 API 路由是否有速率限制。

    检查两层：
    1. 全局限流中间件（RateLimitMiddleware）—— 位于 main.py
    2. 路由级限流装饰器 —— 位于各 routes 文件
    """
    # 先检查是否有全局限流中间件
    main_py = APP_ROOT / "main.py"
    has_global_limiter = False
    global_files: list[str] = []
    if main_py.exists():
        main_content = main_py.read_text(encoding="utf-8")
        if "RateLimitMiddleware" in main_content or "rate_limiter" in main_content.lower():
            has_global_limiter = True
            global_files.append(str(main_py.relative_to(APP_ROOT)))

    api_dir = APP_ROOT / "api"
    total_routers = 0
    has_rate_limit = 0
    rate_files: list[str] = []

    for py_file in _py_files(api_dir):
        content = py_file.read_text(encoding="utf-8")
        if "@router" in content and "def " in content:
            total_routers += 1
            if "rate_limit" in content.lower() or "throttle" in content.lower() or "slowapi" in content.lower():
                has_rate_limit += 1
                rate_files.append(str(py_file.relative_to(APP_ROOT)))

    if has_global_limiter:
        _append(
            findings,
            rule_id="ops_rate_limit_global",
            name="全局速率限制已启用（RateLimitMiddleware）",
            category="rate_limit",
            severity=SEVERITY_LOW,
            count=total_routers,
            file_paths=global_files,
            description=f"已通过全局中间件实现速率限制，所有 {total_routers} 个路由受保护",
        )
        if has_rate_limit > 0:
            _append(
                findings,
                rule_id="ops_rate_limit_route_level",
                name="路由级速率限制（额外保护）",
                category="rate_limit",
                severity=SEVERITY_LOW,
                count=has_rate_limit,
                file_paths=rate_files,
                description=f"{has_rate_limit} 个路由有额外的路由级限流",
            )
        return

    if total_routers > 0 and has_rate_limit == 0:
        _append(
            findings,
            rule_id="ops_no_rate_limit",
            name="所有 API 路由均无数率限制",
            category="rate_limit",
            severity=SEVERITY_HIGH,
            count=total_routers,
            description=f"共 {total_routers} 个路由，0 个有速率限制；建议引入 slowapi 或 FastAPI 内置限流",
        )
    elif has_rate_limit < total_routers:
        _append(
            findings,
            rule_id="ops_partial_rate_limit",
            name="仅部分 API 路由有速率限制",
            category="rate_limit",
            severity=SEVERITY_MEDIUM,
            count=total_routers - has_rate_limit,
            file_paths=rate_files,
            description=f"{has_rate_limit}/{total_routers} 路由有限速，其余路由无保护",
        )


# ======================== 3. 裸 except 块 ========================

def _scan_bare_except(findings: list[OpsFinding]) -> None:
    """检测 except Exception 块，无结构化日志记录。"""
    service_dir = APP_ROOT / "services"
    bare_except_files: list[str] = []
    total_bare_except = 0

    for py_file in _py_files(service_dir):
        content = py_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 匹配 except Exception / except: / except Exception as e
            if re.match(r"^except\s+(Exception|BaseException)?\s*:", stripped) or \
               re.match(r"^except\s+Exception\s+as\s+\w+\s*:", stripped):
                # 检查后续 3 行是否有 logger
                context = "\n".join(lines[i:i + 4])
                if not re.search(r"logger\.|logging\.", context):
                    total_bare_except += 1
                    bare_except_files.append(str(py_file.relative_to(APP_ROOT)))
                    break  # 每个文件只记一次

    if total_bare_except > 0:
        _append(
            findings,
            rule_id="ops_bare_except_no_log",
            name="except 块无结构化日志",
            category="bare_except",
            severity=SEVERITY_HIGH,
            count=total_bare_except,
            file_paths=bare_except_files[:10],
            description=f"共 {total_bare_except} 处 except 块未记录 logger，异常被静默吞没",
        )


# ======================== 4. 缺失日志覆盖 ========================

def _scan_missing_logger(findings: list[OpsFinding]) -> None:
    """检查服务模块是否有 logger。"""
    service_dir = APP_ROOT / "services"
    missing_logger_files: list[str] = []
    total_missing = 0

    for py_file in _py_files(service_dir):
        content = py_file.read_text(encoding="utf-8")
        if "logger = logging.getLogger" not in content and "logger = getLogger" not in content:
            # 排除 __init__.py 和 test 文件
            if py_file.name != "__init__.py" and not py_file.name.startswith("test_"):
                total_missing += 1
                missing_logger_files.append(str(py_file.relative_to(APP_ROOT)))

    if total_missing > 0:
        _append(
            findings,
            rule_id="ops_missing_logger",
            name="服务模块缺少 logger 定义",
            category="missing_logger",
            severity=SEVERITY_MEDIUM,
            count=total_missing,
            file_paths=missing_logger_files[:10],
            description=f"{total_missing} 个服务模块无 logger，异常时无法追踪",
        )


# ======================== 5. 缺失数据库索引 ========================

def _scan_missing_indexes(findings: list[OpsFinding]) -> None:
    """扫描 models.py 中高频查询列是否有显式索引。

    同时检查 alembic 迁移 0033 是否已创建索引（作为修复方案）。
    """
    models_file = APP_ROOT / "db" / "models.py"
    if not models_file.exists():
        return

    content = models_file.read_text(encoding="utf-8")

    # 检查 0033 迁移是否存在
    migration_0033 = APP_ROOT.parent / "alembic" / "versions" / "0033_ops_missing_indexes.py"
    migration_exists = migration_0033.exists()

    # 高频查询列模式：模型类 -> (列名, 展示名)
    high_freq_cols = [
        ("Voucher", "status", "Voucher.status 无索引"),
        ("Voucher", "voucher_date", "Voucher.voucher_date 无索引"),
        ("Voucher", "period_id", "Voucher.period_id 无索引"),
        ("Voucher", "ledger_id", "Voucher.ledger_id 无索引"),
        ("AccountingEntry", "voucher_date", "AccountingEntry.voucher_date 无索引"),
        ("AccountingEntry", "account_code", "AccountingEntry.account_code 无索引"),
        ("AccountingEntry", "review_status", "AccountingEntry.review_status 无索引"),
        ("AccountingEntry", "post_status", "AccountingEntry.post_status 无索引"),
        ("AccountingEntry", "ledger_id", "AccountingEntry.ledger_id 无索引"),
        ("AccountingPeriod", "status", "AccountingPeriod.status 无索引"),
        ("SourceFile", "import_job_id", "SourceFile.import_job_id 无索引"),
    ]

    # 解析 models.py 中哪些列已有显式索引
    indexed_cols: set[tuple[str, str]] = set()
    # mapped_column(..., index=True) 模式
    for cls, col, _ in high_freq_cols:
        if re.search(rf"{col}\s*=\s*mapped_column\([^\)]*index\s*=\s*True", content):
            indexed_cols.add((cls, col))
        if re.search(rf"Index\([^\)]*{col}[^\)]*\)", content):
            indexed_cols.add((cls, col))

    # 如果 0033 迁移存在，进一步检查数据库中是否真实存在对应索引
    if migration_exists:
        try:
            from app.db.session import engine
            from sqlalchemy import inspect
            inspector = inspect(engine)
            for cls, col, desc in high_freq_cols:
                table_name = _table_name_for_model(cls)
                if not table_name:
                    continue
                try:
                    idxs = inspector.get_indexes(table_name)
                    if any(col in idx.get("column_names", []) for idx in idxs):
                        indexed_cols.add((cls, col))
                except Exception:
                    logger.warning(f"无法读取表 {table_name} 的索引信息", exc_info=True)
        except Exception:
            logger.warning("数据库索引检测失败", exc_info=True)

    missing: list[str] = []
    for cls, col, desc in high_freq_cols:
        if (cls, col) not in indexed_cols:
            missing.append(desc)

    if missing:
        severity = SEVERITY_LOW if migration_exists else SEVERITY_MEDIUM
        desc_text = f"{len(missing)} 列无索引"
        if migration_exists:
            desc_text += "（0033 迁移可能未执行或索引未生效）"
        _append(
            findings,
            rule_id="ops_missing_index",
            name="高频查询列缺少显式索引" if not migration_exists else "高频查询列索引（0033 迁移待执行）",
            category="missing_index",
            severity=severity,
            count=len(missing),
            file_paths=[str(models_file.relative_to(APP_ROOT))],
            description=f"{desc_text}：{', '.join(missing[:5])}",
        )


def _table_name_for_model(model_name: str) -> str | None:
    """根据模型名推测表名（常见 snake_case 规则）。"""
    name_map = {
        "Voucher": "vouchers",
        "AccountingEntry": "accounting_entries",
        "AccountingPeriod": "accounting_periods",
        "SourceFile": "source_files",
    }
    return name_map.get(model_name)


# ======================== 6. N+1 查询风险 ========================

def _scan_n_plus_one(findings: list[OpsFinding]) -> None:
    """检测 for 循环内嵌套数据库查询模式。

    区分两类风险：
    1. 高风险：for 循环内部执行 db.query() 或 session.execute() —— 真正的 N+1
    2. 中风险：for 循环头部使用 .all() —— 全量加载到内存，可能导致内存溢出
    """
    service_dir = APP_ROOT / "services"
    high_risk_files: list[str] = []
    med_risk_files: list[str] = []
    total_high = 0
    total_med = 0

    for py_file in _py_files(service_dir):
        # 跳过扫描器自身（源码包含 db.query 字符串）
        if "ops_debt_scan_service" in py_file.name:
            continue
        content = py_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        in_for_loop = False
        loop_var: str | None = None
        for_depth = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过空行和注释
            if not stripped or stripped.startswith("#"):
                continue
            # 检测 for 循环开始（必须是块级 for，以 : 结尾，排除列表推导式）
            if re.match(r"^\s*for\s+\w+\s+in\s+", stripped) and stripped.rstrip().endswith(":"):
                in_for_loop = True
                loop_var_match = re.match(r"^\s*for\s+(\w+)\s+in\s+", stripped)
                loop_var = loop_var_match.group(1) if loop_var_match else None
                for_depth = len(line) - len(line.lstrip())
                # 检查同一行是否有 db.query(...).all() —— 中风险（显式全量加载）
                # 排除带 .filter(...) 的查询：已在数据库层过滤，不是全表加载
                if ".all()" in stripped and "db.query(" in stripped and ".filter(" not in stripped:
                    total_med += 1
                    med_risk_files.append(str(py_file.relative_to(APP_ROOT)))
                continue

            if in_for_loop:
                current_indent = len(line) - len(line.lstrip()) if stripped else 999
                if stripped and current_indent <= for_depth and not stripped.startswith("#"):
                    # 退出 for 循环
                    in_for_loop = False
                    loop_var = None
                    continue

                # 跳过注释行
                if stripped.startswith("#"):
                    continue

                # 检查循环体内是否有 db.query() / session.execute()
                # 排除写操作：db.execute(text(...))、db.execute(sql_delete(...))、db.execute(update/insert/delete)
                # 排除未引用循环变量的查询（固定枚举/配置循环不是数据集 N+1）
                has_read_query = False
                if "db.query(" in stripped or "session.execute(" in stripped:
                    if loop_var is None or loop_var in stripped:
                        has_read_query = True

                # 判断 db.execute 是否为写操作：当前行或前面 5 行出现 UPDATE/INSERT/DELETE/text( 等关键字
                is_write = ("text(" in stripped or "sql_delete" in stripped
                             or "UPDATE " in stripped.upper() or "INSERT " in stripped.upper()
                             or "DELETE " in stripped.upper())
                if not is_write and "db.execute(" in stripped:
                    # 检查前 5 行上下文是否为 DML
                    ctx = "\n".join(lines[max(0, i - 5):i + 1]).upper()
                    if "UPDATE " in ctx or "INSERT " in ctx or "DELETE " in ctx or "TEXT(\"UPDATE" in ctx or "TEXT('UPDATE" in ctx:
                        is_write = True

                has_write_execute = False
                if "db.execute(" in stripped and not is_write:
                    if loop_var is None or loop_var in stripped:
                        has_write_execute = True

                if has_read_query or has_write_execute:
                    total_high += 1
                    high_risk_files.append(str(py_file.relative_to(APP_ROOT)))
                    in_for_loop = False  # 每个文件只记一次

    if total_high > 0:
        _append(
            findings,
            rule_id="ops_n_plus_one_query",
            name="for 循环内执行数据库查询（真正的 N+1）",
            category="n_plus_one",
            severity=SEVERITY_HIGH,
            count=total_high,
            file_paths=high_risk_files[:10],
            description="for 循环内执行 db.query()，每次迭代触发一次 DB 查询，O(N) 复杂度",
        )

    if total_med > 0:
        _append(
            findings,
            rule_id="ops_full_load_risk",
            name="for 循环全量加载（内存风险）",
            category="n_plus_one",
            severity=SEVERITY_LOW,
            count=total_med,
            file_paths=med_risk_files[:10],
            description="for 循环直接 .all() 全量加载，数据量大时可能导致内存溢出；建议分页或分批处理",
        )


# ======================== 公开 API ========================

def scan_ops_debt(
    *,
    categories: list[str] | None = None,
) -> OpsReport:
    """执行运维负债扫描，返回结构化报告。

    Args:
        categories: 可选，仅扫描指定类别。可选值：
            health_check / rate_limit / bare_except / missing_logger / missing_index / n_plus_one
    """
    categories_set = set(categories) if categories else None
    findings: list[OpsFinding] = []

    if categories_set is None or "health_check" in categories_set:
        _scan_health_check(findings)
    if categories_set is None or "rate_limit" in categories_set:
        _scan_rate_limit(findings)
    if categories_set is None or "bare_except" in categories_set:
        _scan_bare_except(findings)
    if categories_set is None or "missing_logger" in categories_set:
        _scan_missing_logger(findings)
    if categories_set is None or "missing_index" in categories_set:
        _scan_missing_indexes(findings)
    if categories_set is None or "n_plus_one" in categories_set:
        _scan_n_plus_one(findings)

    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (sev_order.get(f.severity, 99), f.category, -f.count))

    return OpsReport(
        generated_at=datetime.now(timezone.utc),
        findings=findings,
    )
