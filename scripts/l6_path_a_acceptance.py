#!/usr/bin/env python3
"""L6 路径 A 记账主线端到端验收脚本。

覆盖：注册 -> 团队 -> 账簿 -> 期间 -> 凭证录入 -> 复核 -> 过账 ->
      损益结转 -> 结账 -> 报表核对。
输出：控制台 + JSON 报告到 /tmp/l6_path_a_report.json
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"
REPORT_PATH = Path("scripts/l6_path_a_report.json")


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


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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
    print("L6 路径 A 记账主线端到端验收 — 开始")
    print(f"目标: {BASE}")
    wait_for_backend()

    suffix = uuid.uuid4().hex[:8]
    username = f"l6a_{suffix}"
    password = "TestPass123!"

    with httpx.Client(base_url=BASE, timeout=30) as c:
        # A1: 注册
        reg = c.post(
            "/api/auth/register",
            json={
                "username": username,
                "password": password,
                "agreed_terms": True,
                "agreed_privacy": True,
            },
        )
        record("A1", "注册新用户", reg.status_code == 200, f"status={reg.status_code}")
        if reg.status_code != 200:
            print(reg.text)
            return 1

        # A2: 登录
        login = c.post(
            "/api/auth/login/password",
            json={"username": username, "password": password},
        )
        token = login.json().get("access_token") if login.status_code == 200 else None
        record("A2", "登录获取 Token", bool(token))
        if not token:
            print(login.text)
            return 1

        # A3: 创建团队
        team = c.post(
            "/api/teams",
            headers=headers(token),
            json={"name": f"L6A团队{suffix}", "type": "enterprise"},
        )
        team_id = team.json().get("id") if team.status_code == 200 else None
        record("A3", "创建团队", bool(team_id), f"team_id={team_id}")

        # A4: 创建账簿
        ledger = c.post(
            "/api/ledgers",
            headers=headers(token),
            json={
                "team_id": team_id,
                "name": f"L6A账簿{suffix}",
                "accounting_start_date": "2026-01-01",
            },
        )
        ledger_id = ledger.json().get("id") if ledger.status_code == 200 else None
        record("A4", "创建账簿", bool(ledger_id), f"ledger_id={ledger_id}")
        if not ledger_id:
            print(ledger.text)
            return 1

        # A5: 获取期间
        periods = c.get(
            "/api/accounting-periods",
            headers=headers(token),
            params={"ledger_id": ledger_id},
        )
        period = periods.json()[0] if periods.status_code == 200 and periods.json() else None
        period_id = period.get("id") if period else None
        org_id = period.get("organization_id") if period else None
        record("A5", "获取首个会计期间", bool(period_id), f"period_id={period_id}, org_id={org_id}")
        if not period_id:
            print(periods.text)
            return 1

        # A6: 创建收入凭证
        vno_rev = f"记-{suffix}-001"
        rev = c.post(
            "/api/vouchers",
            headers=headers(token),
            json={
                "ledger_id": ledger_id,
                "organization_id": org_id,
                "period_id": period_id,
                "voucher_type": "记",
                "voucher_number": vno_rev,
                "voucher_date": "2026-01-15",
                "summary": "销售商品确认收入",
                "lines": [
                    {
                        "line_no": 1,
                        "summary": "应收账款-客户A",
                        "account_code": "1122",
                        "account_name": "应收账款",
                        "debit_amount": "1130.00",
                        "credit_amount": "0.00",
                        "counterparty": "客户A",
                    },
                    {
                        "line_no": 2,
                        "summary": "主营业务收入",
                        "account_code": "6001",
                        "account_name": "主营业务收入",
                        "debit_amount": "0.00",
                        "credit_amount": "1000.00",
                    },
                    {
                        "line_no": 3,
                        "summary": "销项税额",
                        "account_code": "22210107",
                        "account_name": "应交税费-应交增值税-销项税额",
                        "debit_amount": "0.00",
                        "credit_amount": "130.00",
                    },
                ],
            },
        )
        rev_id = rev.json().get("data", {}).get("voucher_id") if rev.status_code == 201 else None
        record("A6", "创建收入凭证", bool(rev_id), f"voucher_id={rev_id}")
        if not rev_id:
            print(rev.text)

        # A7: 创建费用凭证
        vno_exp = f"记-{suffix}-002"
        exp = c.post(
            "/api/vouchers",
            headers=headers(token),
            json={
                "ledger_id": ledger_id,
                "organization_id": org_id,
                "period_id": period_id,
                "voucher_type": "记",
                "voucher_number": vno_exp,
                "voucher_date": "2026-01-20",
                "summary": "支付办公费",
                "lines": [
                    {
                        "line_no": 1,
                        "summary": "管理费用-办公费",
                        "account_code": "6602",
                        "account_name": "管理费用",
                        "debit_amount": "500.00",
                        "credit_amount": "0.00",
                    },
                    {
                        "line_no": 2,
                        "summary": "银行存款",
                        "account_code": "1002",
                        "account_name": "银行存款",
                        "debit_amount": "0.00",
                        "credit_amount": "500.00",
                    },
                ],
            },
        )
        exp_id = exp.json().get("data", {}).get("voucher_id") if exp.status_code == 201 else None
        record("A7", "创建费用凭证", bool(exp_id), f"voucher_id={exp_id}")
        if not exp_id:
            print(exp.text)

        # A8: 复核两张凭证
        for vid, name in [(rev_id, "收入"), (exp_id, "费用")]:
            if vid:
                r = c.post(f"/api/vouchers/{vid}/verify", headers=headers(token))
                record(f"A8-{name}", f"复核{name}凭证", r.status_code == 200)

        # A9: 过账两张凭证
        for vid, name in [(rev_id, "收入"), (exp_id, "费用")]:
            if vid:
                r = c.post(f"/api/vouchers/{vid}/post", headers=headers(token))
                record(f"A9-{name}", f"过账{name}凭证", r.status_code == 200)

        # A10: 损益结转
        pl = c.post(f"/api/accounting-periods/{period_id}/pl-transfer", headers=headers(token))
        record("A10", "损益结转", pl.status_code == 200, f"status={pl.status_code}")
        if pl.status_code != 200:
            print(pl.text)

        # A11: 结账
        close = c.post(f"/api/accounting-periods/{period_id}/close", headers=headers(token))
        record("A11", "会计期间结账", close.status_code == 200, f"status={close.status_code}")
        if close.status_code != 200:
            print(close.text)

        # A12: 资产负债表
        bs = c.get(
            "/api/reports/balance-sheet",
            headers=headers(token),
            params={"ledger_id": ledger_id, "period_id": period_id},
        )
        bs_ok = bs.status_code == 200
        bs_data = bs.json() if bs_ok else {}
        total_assets = Decimal(str(bs_data.get("total_assets", 0)))
        total_liabilities = Decimal(str(bs_data.get("total_liabilities", 0)))
        total_equity = Decimal(str(bs_data.get("total_equity", 0)))
        balanced = total_assets == (total_liabilities + total_equity)
        record(
            "A12",
            "资产负债表平衡",
            bs_ok and balanced,
            f"assets={total_assets}, liab+equity={total_liabilities + total_equity}",
        )

        # A13: 利润表
        is_ = c.get(
            "/api/reports/income-statement",
            headers=headers(token),
            params={"ledger_id": ledger_id, "period_id": period_id},
        )
        is_ok = is_.status_code == 200
        is_data = is_.json() if is_ok else {}
        net_profit = Decimal(str(is_data.get("net_profit", 0)))
        record("A13", "利润表净利润", is_ok, f"net_profit={net_profit}")

        # A14: 试算平衡
        tb = c.get(
            "/api/reports/trial-balance",
            headers=headers(token),
            params={"ledger_id": ledger_id, "period_id": period_id},
        )
        tb_ok = tb.status_code == 200
        tb_data = tb.json() if tb_ok else {}
        tb_balanced = tb_data.get("is_balanced") if isinstance(tb_data, dict) else False
        record("A14", "试算平衡", tb_ok and tb_balanced)

    passed = sum(1 for s in steps if s.ok)
    failed = sum(1 for s in steps if not s.ok)
    print(f"\n{'='*50}")
    print(f"合计: {passed} 通过, {failed} 失败 / {len(steps)} 项")

    report = {
        "title": "L6 路径 A 记账主线端到端验收",
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
