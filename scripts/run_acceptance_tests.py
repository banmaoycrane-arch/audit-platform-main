#!/usr/bin/env python3
"""Live API acceptance tests for three business paths + opening balances."""

from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass

import httpx

BASE = "http://127.0.0.1:8000"
PASS = "PASS"
FAIL = "FAIL"


@dataclass
class Result:
    case_id: str
    name: str
    status: str
    detail: str = ""


results: list[Result] = []


def record(case_id: str, name: str, ok: bool, detail: str = "") -> None:
    results.append(Result(case_id, name, PASS if ok else FAIL, detail))
    mark = "✓" if ok else "✗"
    print(f"  [{mark}] {case_id}: {name}" + (f" — {detail}" if detail else ""))


def login(client: httpx.Client, username: str, password: str = "testpass123") -> str:
    resp = client.post(
        "/api/auth/login/password",
        json={"username": username, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def auth_headers(token: str, ledger_id: int | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if ledger_id is not None:
        headers["X-Ledger-Id"] = str(ledger_id)
    return headers


def run_path1(client: httpx.Client) -> None:
    print("\n=== 路径一：注册 + 用户上下文 / onboarding ===")
    suffix = uuid.uuid4().hex[:8]
    username = f"accept_{suffix}"
    password = "testpass123"

    reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    record("P1-1", "新用户注册", reg.status_code == 200, f"status={reg.status_code}")

    token = login(client, username, password)
    record("P1-2", "注册后登录", bool(token))

    ctx = client.get("/api/auth/context", headers=auth_headers(token))
    record("P1-3", "获取用户上下文", ctx.status_code == 200)
    if ctx.status_code == 200:
        body = ctx.json()
        record(
            "P1-4",
            "新用户需 onboarding",
            body.get("requires_onboarding") is True,
            f"next_action={body.get('next_action')}",
        )


def run_path2(client: httpx.Client) -> None:
    print("\n=== 路径二：记账流程（账簿范围 + 复核状态） ===")
    token = login(client, "test_runner_001")
    ledgers = client.get("/api/ledgers", headers=auth_headers(token))
    record("P2-1", "获取账簿列表", ledgers.status_code == 200)
    ledger_list = ledgers.json() if ledgers.status_code == 200 else []
    record("P2-2", "至少两个账簿", len(ledger_list) >= 2, f"count={len(ledger_list)}")

    ledger_a = next((l for l in ledger_list if l.get("name") == "2026山西尚德鑫"), ledger_list[0] if ledger_list else None)
    ledger_b = next((l for l in ledger_list if l.get("name") == "新建账簿"), ledger_list[-1] if ledger_list else None)
    if not ledger_a or not ledger_b:
        ledger_a, ledger_b = ledger_list[0], ledger_list[-1]

    for lid in [ledger_a["id"], ledger_b["id"]]:
        periods = client.get(
            "/api/accounting-periods",
            headers=auth_headers(token, lid),
            params={"ledger_id": lid},
        )
        record(f"P2-3-L{lid}", f"账簿 {lid} 会计期间", periods.status_code == 200)

    switch = client.post(
        f"/api/ledgers/{ledger_a['id']}/switch",
        headers=auth_headers(token),
    )
    record("P2-4", "切换当前账簿", switch.status_code == 200)

    entries_a = client.get(
        "/api/entries",
        headers=auth_headers(token, ledger_a["id"]),
        params={"ledger_id": ledger_a["id"], "limit": 5},
    )
    record("P2-5", "按账簿查询凭证", entries_a.status_code == 200)

    periods = client.get(
        "/api/accounting-periods",
        headers=auth_headers(token, ledger_a["id"]),
        params={"ledger_id": ledger_a["id"]},
    ).json()
    period_id = periods[0]["id"] if periods else None
    entry_id = None
    if period_id:
        vno = f"AT-{uuid.uuid4().hex[:6]}"
        manual = client.post(
            "/api/import-jobs/manual-entries",
            headers=auth_headers(token, ledger_a["id"]),
            json={
                "period_id": period_id,
                "drafts": [
                    {
                        "entry_line_no": 1,
                        "summary": "验收测试借方",
                        "account_code": "1002",
                        "account_name": "银行存款",
                        "debit_amount": 100,
                        "credit_amount": 0,
                        "voucher_no": vno,
                        "voucher_date": "2026-01-15",
                    },
                    {
                        "entry_line_no": 2,
                        "summary": "验收测试贷方",
                        "account_code": "2202",
                        "account_name": "应付账款",
                        "debit_amount": 0,
                        "credit_amount": 100,
                        "voucher_no": vno,
                        "voucher_date": "2026-01-15",
                    },
                ],
            },
        )
        if manual.status_code == 200:
            ids = manual.json().get("entry_ids") or []
            entry_id = ids[0] if ids else None
        else:
            record("P2-5b", "人工凭证创建", False, f"status={manual.status_code} {manual.text[:120]}")

    if not entry_id and entries_a.status_code == 200 and entries_a.json():
        entry_id = entries_a.json()[0]["id"]

    if entry_id:
        review = client.patch(
            f"/api/entries/{entry_id}/review",
            headers=auth_headers(token, ledger_a["id"]),
            json={"review_status": "verified"},
        )
        record(
            "P2-6",
            "Step4 复核状态持久化",
            review.status_code == 200 and review.json().get("review_status") == "verified",
            f"entry_id={entry_id}",
        )
    else:
        record("P2-6", "Step4 复核状态持久化", False, "无法创建或获取凭证")


def run_path3(client: httpx.Client) -> None:
    print("\n=== 路径三：审计流程（序时簿 / 导入任务） ===")
    token = login(client, "test_runner_001")
    ledgers = client.get("/api/ledgers", headers=auth_headers(token)).json()
    ledger_id = ledgers[0]["id"] if ledgers else 4

    jobs = client.get(
        "/api/import-jobs",
        headers=auth_headers(token, ledger_id),
        params={"ledger_id": ledger_id, "limit": 10},
    )
    record("P3-1", "查询导入任务（含 jobId）", jobs.status_code == 200)

    daybook = client.get(
        "/api/audit/day-book",
        headers=auth_headers(token, ledger_id),
        params={"ledger_id": ledger_id},
    )
    record("P3-2", "审计序时簿接口", daybook.status_code in (200, 404))

    job_id = None
    if jobs.status_code == 200 and jobs.json():
        job_id = jobs.json()[0].get("id")
    if not job_id:
        job_id = 6  # fallback to completed job in seed DB

    run_test = client.post(f"/api/audit-tests/{job_id}/run", headers=auth_headers(token, ledger_id))
    record("P3-3a", "执行审计测试", run_test.status_code == 200, f"job_id={job_id}")

    findings = client.get(f"/api/audit-tests/{job_id}/findings", headers=auth_headers(token, ledger_id))
    record(
        "P3-3",
        "审计发现列表",
        findings.status_code == 200,
        f"count={len(findings.json()) if findings.status_code == 200 else findings.status_code}",
    )


def run_opening_balances(client: httpx.Client) -> None:
    print("\n=== 期初余额：账簿隔离 ===")
    token = login(client, "test_runner_001")
    ledgers = client.get("/api/ledgers", headers=auth_headers(token)).json()
    if len(ledgers) < 2:
        record("OB-0", "至少两个账簿", False)
        return
    ledger_a, ledger_b = ledgers[0], ledgers[1]
    lid_a, lid_b = ledger_a["id"], ledger_b["id"]

    periods_a = client.get(
        "/api/accounting-periods",
        headers=auth_headers(token, lid_a),
        params={"ledger_id": lid_a},
    ).json()
    periods_b = client.get(
        "/api/accounting-periods",
        headers=auth_headers(token, lid_b),
        params={"ledger_id": lid_b},
    ).json()
    if not periods_a or not periods_b:
        record("OB-0", "两账簿均有期间", False)
        return

    pid_a, pid_b = periods_a[0]["id"], periods_b[0]["id"]
    org_a = periods_a[0].get("organization_id") or periods_a[0].get("org_id")
    org_b = periods_b[0].get("organization_id") or periods_b[0].get("org_id")

    # Set distinct balances per ledger
    bulk_a = client.post(
        "/api/opening-balances/bulk",
        json={
            "organization_id": org_a,
            "period_id": pid_a,
            "ledger_id": lid_a,
            "items": [
                {"account_code": "1002", "debit_balance": 11111, "credit_balance": 0},
                {"account_code": "2202", "debit_balance": 0, "credit_balance": 11111},
            ],
        },
    )
    record("OB-1", "账簿A写入期初", bulk_a.status_code == 200)

    bulk_b = client.post(
        "/api/opening-balances/bulk",
        json={
            "organization_id": org_b,
            "period_id": pid_b,
            "ledger_id": lid_b,
            "items": [
                {"account_code": "1002", "debit_balance": 22222, "credit_balance": 0},
                {"account_code": "2202", "debit_balance": 0, "credit_balance": 22222},
            ],
        },
    )
    record("OB-2", "账簿B写入期初", bulk_b.status_code == 200)

    list_a = client.get(
        "/api/opening-balances",
        params={"organization_id": org_a, "period_id": pid_a, "ledger_id": lid_a},
    ).json()
    list_b = client.get(
        "/api/opening-balances",
        params={"organization_id": org_b, "period_id": pid_b, "ledger_id": lid_b},
    ).json()

    debit_a = next((x["debit_balance"] for x in list_a if x["account_code"] == "1002"), None)
    debit_b = next((x["debit_balance"] for x in list_b if x["account_code"] == "1002"), None)
    record(
        "OB-3",
        "两账簿期初互不影响",
        debit_a == 11111 and debit_b == 22222,
        f"A={debit_a}, B={debit_b}",
    )

    trial_a = client.get(
        "/api/opening-balances/trial-balance",
        params={"organization_id": org_a, "period_id": pid_a, "ledger_id": lid_a},
    ).json()
    trial_b = client.get(
        "/api/opening-balances/trial-balance",
        params={"organization_id": org_b, "period_id": pid_b, "ledger_id": lid_b},
    ).json()
    record(
        "OB-4",
        "试算平衡按账簿独立",
        trial_a.get("is_balanced") and trial_b.get("is_balanced"),
        f"A balanced={trial_a.get('is_balanced')}, B balanced={trial_b.get('is_balanced')}",
    )

    # Wrong ledger_id should not return other ledger's data
    cross = client.get(
        "/api/opening-balances",
        params={"organization_id": org_a, "period_id": pid_a, "ledger_id": lid_b},
    )
    cross_body = cross.json() if cross.status_code == 200 else []
    cross_debit = next((x["debit_balance"] for x in cross_body if x.get("account_code") == "1002"), 0)
    record(
        "OB-5",
        "错账簿ID不串数据",
        cross_debit != debit_a,
        f"cross_debit={cross_debit}, expected != {debit_a}",
    )


def main() -> int:
    print("审计平台验收测试 — 开始")
    print(f"目标: {BASE}")

    # Wait for backend
    for _ in range(10):
        try:
            r = httpx.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    else:
        print("后端未就绪")
        return 1

    with httpx.Client(base_url=BASE, timeout=30) as client:
        run_path1(client)
        run_path2(client)
        run_path3(client)
        run_opening_balances(client)

    passed = sum(1 for r in results if r.status == PASS)
    failed = sum(1 for r in results if r.status == FAIL)
    print(f"\n{'='*50}")
    print(f"合计: {passed} 通过, {failed} 失败 / {len(results)} 项")
    if failed:
        print("\n失败项:")
        for r in results:
            if r.status == FAIL:
                print(f"  - {r.case_id} {r.name}: {r.detail}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
