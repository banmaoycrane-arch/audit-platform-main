#!/usr/bin/env python3
"""L6 路径 B 审计主线端到端验收脚本。

覆盖：注册 -> 团队 -> 账簿 -> 项目 -> 审计任务 -> 导入分录 ->
      审计测试 -> 审计发现 -> 工作底稿 -> 底稿导出。
输出：控制台 + JSON 报告到 l6_path_b_report.json
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
REPORT_PATH = Path("scripts/l6_path_b_report.json")


@dataclass
class Step:
    id: str
    name: str
    ok: bool
    detail: str = ""


steps: list[Step] = []


def record(step_id: str, name: str, ok: bool, detail: str = "") -> None:
    steps.append(Step(step_id, name, ok, detail))
    mark = "✓" if ok else "✗"
    print(f"  [{mark}] {step_id}: {name}" + (f" — {detail}" if detail else ""))


def headers(token: str, ledger_id: int | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if ledger_id is not None:
        h["X-Ledger-Id"] = str(ledger_id)
    return h


def wait_for_backend() -> None:
    for _ in range(20):
        try:
            r = httpx.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("后端未就绪")


def main() -> int:
    print("L6 路径 B 审计主线端到端验收 — 开始")
    print(f"目标: {BASE}")
    wait_for_backend()

    suffix = uuid.uuid4().hex[:8]
    username = f"l6b_{suffix}"
    password = "TestPass123!"

    with httpx.Client(base_url=BASE, timeout=30) as c:
        # B1: 注册
        reg = c.post(
            "/api/auth/register",
            json={
                "username": username,
                "password": password,
                "agreed_terms": True,
                "agreed_privacy": True,
            },
        )
        record("B1", "注册新用户", reg.status_code == 200)
        if reg.status_code != 200:
            print(reg.text)
            return 1

        # B2: 登录
        login = c.post(
            "/api/auth/login/password",
            json={"username": username, "password": password},
        )
        token = login.json().get("access_token") if login.status_code == 200 else None
        record("B2", "登录获取 Token", bool(token))
        if not token:
            print(login.text)
            return 1

        # B3: 创建团队
        team = c.post(
            "/api/teams",
            headers=headers(token),
            json={"name": f"L6B团队{suffix}", "type": "enterprise"},
        )
        team_id = team.json().get("id") if team.status_code == 200 else None
        record("B3", "创建团队", bool(team_id), f"team_id={team_id}")

        # B4: 创建账簿
        ledger = c.post(
            "/api/ledgers",
            headers=headers(token),
            json={
                "team_id": team_id,
                "name": f"L6B账簿{suffix}",
                "accounting_start_date": "2026-01-01",
            },
        )
        ledger_id = ledger.json().get("id") if ledger.status_code == 200 else None
        record("B4", "创建账簿", bool(ledger_id), f"ledger_id={ledger_id}")
        if not ledger_id:
            print(ledger.text)
            return 1

        # B5: 创建审计项目
        project = c.post(
            "/api/projects",
            headers=headers(token),
            json={
                "team_id": team_id,
                "name": f"L6B审计项目{suffix}",
                "project_type": "audit",
                "status": "active",
            },
        )
        project_id = project.json().get("id") if project.status_code == 200 else None
        record("B5", "创建审计项目", bool(project_id), f"project_id={project_id}")
        if not project_id:
            print(project.text)
            return 1

        # B6: 项目关联账簿
        assoc = c.post(
            f"/api/projects/{project_id}/ledgers",
            headers=headers(token),
            json={"ledger_id": ledger_id},
        )
        record("B6", "项目关联账簿", assoc.status_code == 200)

        # B7: 获取期间
        periods = c.get(
            "/api/accounting-periods",
            headers=headers(token),
            params={"ledger_id": ledger_id},
        )
        period = periods.json()[0] if periods.status_code == 200 and periods.json() else None
        period_id = period.get("id") if period else None
        org_id = period.get("organization_id") if period else None
        record("B7", "获取会计期间", bool(period_id), f"period_id={period_id}")
        if not period_id:
            print(periods.text)
            return 1

        # B8: 通过 manual-entries 导入审计分录（模拟序时簿导入）
        vno = f"记-{suffix}-001"
        manual = c.post(
            "/api/import-jobs/manual-entries",
            headers=headers(token),
            json={
                "period_id": period_id,
                "organization_name": f"L6B被审计单位{suffix}",
                "drafts": [
                    {
                        "voucher_no": vno,
                        "voucher_date": "2026-01-15",
                        "summary": "收到客户货款",
                        "account_code": "1002",
                        "account_name": "银行存款",
                        "debit_amount": 1000,
                        "credit_amount": 0,
                        "counterparty": "客户A",
                        "entry_line_no": 1,
                        "metadata": {"source": "manual_entry"},
                        "tags": [],
                    },
                    {
                        "voucher_no": vno,
                        "voucher_date": "2026-01-15",
                        "summary": "应收账款核销",
                        "account_code": "1122",
                        "account_name": "应收账款",
                        "debit_amount": 0,
                        "credit_amount": 1000,
                        "counterparty": "客户A",
                        "entry_line_no": 2,
                        "metadata": {"source": "manual_entry"},
                        "tags": [],
                    },
                ],
            },
        )
        job_id = manual.json().get("job_id") if manual.status_code == 200 else None
        entry_count = manual.json().get("count", 0) if manual.status_code == 200 else 0
        record(
            "B8",
            "导入审计分录",
            bool(job_id) and entry_count == 2,
            f"job_id={job_id}, entries={entry_count}",
        )
        if not job_id:
            print(manual.text)
            return 1

        # B9: 创建审计任务
        task = c.post(
            "/api/audit/tasks",
            headers=headers(token),
            json={
                "project_id": project_id,
                "ledger_id": ledger_id,
                "title": f"L6B测试任务{suffix}",
                "description": "审计主线端到端验收",
                "task_type": "substantive",
                "audit_area": "收入循环",
                "priority": "high",
            },
        )
        task_id = task.json().get("id") if task.status_code == 201 else None
        record("B9", "创建审计任务", bool(task_id), f"task_id={task_id}")

        # B10: 运行审计测试
        run = c.post(f"/api/audit-tests/{job_id}/run", headers=headers(token))
        run_ok = run.status_code == 200
        findings_count = len(run.json().get("findings", [])) if run_ok else 0
        record("B10", "执行审计测试", run_ok, f"findings={findings_count}")
        if not run_ok:
            print(run.text)

        # B11: 查询审计发现
        findings = c.get(f"/api/audit-tests/{job_id}/findings", headers=headers(token))
        record("B11", "查询审计发现", findings.status_code == 200, f"count={len(findings.json())}")

        # B12: 创建审计工作底稿索引
        wp = c.post(
            "/api/workpapers/index",
            headers=headers(token, ledger_id),
            json={
                "title": f"L6B收入循环底稿{suffix}",
                "audit_area": "收入循环",
                "project_id": project_id,
            },
        )
        wp_id = wp.json().get("id") if wp.status_code == 201 else None
        record("B12", "创建工作底稿索引", bool(wp_id), f"index_id={wp_id}")

        # B13: 导出工作底稿目录
        export = c.get("/api/workpapers/export", headers=headers(token, ledger_id))
        record("B13", "导出工作底稿目录", export.status_code == 200)

    passed = sum(1 for s in steps if s.ok)
    failed = sum(1 for s in steps if not s.ok)
    print(f"\n{'='*50}")
    print(f"合计: {passed} 通过, {failed} 失败 / {len(steps)} 项")

    report = {
        "title": "L6 路径 B 审计主线端到端验收",
        "base_url": BASE,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {"passed": passed, "failed": failed, "total": len(steps)},
        "steps": [{"id": s.id, "name": s.name, "status": "PASS" if s.ok else "FAIL", "detail": s.detail} for s in steps],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写入: {REPORT_PATH}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
