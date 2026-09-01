#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块功能：灌入演示/验收用样例账套（解决生产「有用户无分录」空洞）
业务场景：本地、staging 或经批准的生产环境，补齐团队/账簿/期间/借贷平衡凭证/事件工单
政策依据：样例数据仅用于结构验证与演示，不构成正式账；正式结论仍需 L6 人工签字
输入数据：HTTP API（默认 http://127.0.0.1:8000）
输出结果：控制台打印账号、账簿 ID、凭证与事件编号
创建日期：2026-08-02
更新记录：
    2026-08-02  首版样例账：注册→团队→账簿→期间→两张平衡凭证→两个事件工单

用法：
    python scripts/seed_demo_ledger.py
    BASE_URL=https://47.122.117.76:8443 python scripts/seed_demo_ledger.py

环境变量：
    BASE_URL   后端地址，默认 http://127.0.0.1:8000
    DEMO_USER  用户名，默认 demo_sample_001
    DEMO_PASS  密码，默认 DemoPass123!
"""
from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal

import httpx

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERNAME = os.environ.get("DEMO_USER", "demo_sample_001")
PASSWORD = os.environ.get("DEMO_PASS", "DemoPass123!")


def money(value: str) -> str:
    return str(Decimal(value).quantize(Decimal("0.00")))


def main() -> int:
    suffix = uuid.uuid4().hex[:6]
    client = httpx.Client(base_url=BASE, timeout=45, verify=False)

    health = client.get("/health")
    if health.status_code != 200:
        print(f"后端未就绪: {BASE} status={health.status_code}")
        return 1

    reg = client.post(
        "/api/auth/register",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    if reg.status_code not in (200, 400, 409):
        print(f"注册失败: {reg.status_code} {reg.text}")
        return 1

    login = client.post(
        "/api/auth/login/password",
        json={"username": USERNAME, "password": PASSWORD},
    )
    token = (login.json() or {}).get("access_token")
    if not token:
        print(f"登录失败: {login.status_code} {login.text}")
        return 1
    headers = {"Authorization": f"Bearer {token}"}

    # 团队
    team = client.post(
        "/api/teams",
        headers=headers,
        json={"name": f"样例演示团队-{suffix}", "type": "company"},
    )
    if team.status_code != 200:
        # 已有团队则取第一个
        teams = client.get("/api/teams", headers=headers)
        items = teams.json() if teams.status_code == 200 else []
        if isinstance(items, dict):
            items = items.get("items") or items.get("teams") or []
        if not items:
            print(f"创建团队失败: {team.text}")
            return 1
        team_id = items[0]["id"]
        print(f"复用已有团队 id={team_id}")
    else:
        team_id = team.json()["id"]
        print(f"创建团队 id={team_id}")

    # 账簿
    ledger_name = f"样例账簿-演示-{suffix}"
    ledger_resp = client.post(
        "/api/ledgers",
        headers=headers,
        json={"name": ledger_name, "team_id": team_id},
    )
    if ledger_resp.status_code != 200:
        print(f"创建账簿失败: {ledger_resp.text}")
        return 1
    ledger_id = ledger_resp.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    h = {**headers, "X-Ledger-Id": str(ledger_id)}
    print(f"创建账簿 id={ledger_id} name={ledger_name}")

    # 会计期间 2026-01
    period = client.post(
        "/api/accounting-periods",
        headers=h,
        json={
            "ledger_id": ledger_id,
            "period_code": "2026-01",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "period_type": "monthly",
        },
    )
    if period.status_code not in (200, 201):
        print(f"创建期间失败（可继续若已有期间）: {period.status_code} {period.text}")
        period_id = None
        organization_id = None
    else:
        period_body = period.json()
        period_id = period_body.get("id")
        organization_id = period_body.get("organization_id")
        print(f"创建期间 id={period_id} org={organization_id}")

    if organization_id is None:
        # 从账簿详情兜底
        ledger_detail = client.get(f"/api/ledgers/{ledger_id}", headers=h)
        if ledger_detail.status_code == 200:
            organization_id = ledger_detail.json().get("organization_id")
    if organization_id is None:
        print("无法解析 organization_id，跳过凭证创建，仅保留事件样例")
        created_voucher_ids = []
    else:
        # 两张借贷平衡凭证（销售收款 + 采购付款）
        vouchers = [
            {
                "ledger_id": ledger_id,
                "organization_id": organization_id,
                "period_id": period_id,
                "voucher_type": "记",
                "voucher_number": f"{suffix}-001",
                "voucher_date": "2026-01-15",
                "summary": "样例：销售收款",
                "lines": [
                    {
                        "line_no": 1,
                        "account_code": "1002",
                        "account_name": "银行存款",
                        "summary": "收到货款",
                        "debit_amount": money("11300.00"),
                        "credit_amount": money("0.00"),
                    },
                    {
                        "line_no": 2,
                        "account_code": "6001",
                        "account_name": "主营业务收入",
                        "summary": "确认收入",
                        "debit_amount": money("0.00"),
                        "credit_amount": money("10000.00"),
                    },
                    {
                        "line_no": 3,
                        "account_code": "2221",
                        "account_name": "应交税费-销项税额",
                        "summary": "销项税",
                        "debit_amount": money("0.00"),
                        "credit_amount": money("1300.00"),
                    },
                ],
            },
            {
                "ledger_id": ledger_id,
                "organization_id": organization_id,
                "period_id": period_id,
                "voucher_type": "记",
                "voucher_number": f"{suffix}-002",
                "voucher_date": "2026-01-20",
                "summary": "样例：采购付款",
                "lines": [
                    {
                        "line_no": 1,
                        "account_code": "1405",
                        "account_name": "库存商品",
                        "summary": "采购入库",
                        "debit_amount": money("5000.00"),
                        "credit_amount": money("0.00"),
                    },
                    {
                        "line_no": 2,
                        "account_code": "2221",
                        "account_name": "应交税费-进项税额",
                        "summary": "进项税",
                        "debit_amount": money("650.00"),
                        "credit_amount": money("0.00"),
                    },
                    {
                        "line_no": 3,
                        "account_code": "1002",
                        "account_name": "银行存款",
                        "summary": "支付货款",
                        "debit_amount": money("0.00"),
                        "credit_amount": money("5650.00"),
                    },
                ],
            },
        ]

        created_voucher_ids = []
        for payload in vouchers:
            body = {k: v for k, v in payload.items() if v is not None}
            resp = client.post("/api/vouchers", headers=h, json=body)
            if resp.status_code not in (200, 201):
                print(f"创建凭证失败 {payload['voucher_number']}: {resp.status_code} {resp.text}")
                return 1
            data = resp.json()
            vid = (data.get("data") or data).get("id")
            created_voucher_ids.append(vid)
            print(f"创建凭证 id={vid} no={payload['voucher_number']}")

    # 查询分录并挂到事件
    entries_resp = client.get(f"/api/entries?ledger_id={ledger_id}&limit=50", headers=h)
    entry_ids: list[int] = []
    if entries_resp.status_code == 200:
        data = entries_resp.json()
        rows = data if isinstance(data, list) else (data.get("items") or data.get("entries") or [])
        entry_ids = [row["id"] for row in rows if isinstance(row, dict) and "id" in row]

    events = [
        {
            "title": "样例事件：销售收款闭环",
            "event_type": "revenue_recognition",
            "occurred_on": "2026-01-15",
            "summary": "向客户销售商品并收到银行存款，含销项税。用于演示事件工单与相似推荐。",
            "source": "manual",
        },
        {
            "title": "样例事件：采购付款闭环",
            "event_type": "purchase",
            "occurred_on": "2026-01-20",
            "summary": "采购库存商品并支付银行存款，含进项税。用于演示事件聚类与向量推荐。",
            "source": "manual",
        },
    ]
    event_ids: list[int] = []
    for idx, ev in enumerate(events):
        resp = client.post("/api/economic-events/", headers=h, json=ev)
        if resp.status_code not in (200, 201):
            print(f"创建事件失败: {resp.status_code} {resp.text}")
            return 1
        eid = resp.json()["id"]
        event_ids.append(eid)
        print(f"创建事件 id={eid} no={resp.json().get('event_no')}")
        # 挂分录（有则挂）
        if entry_ids:
            attach_id = entry_ids[min(idx, len(entry_ids) - 1)]
            attach = client.post(
                f"/api/economic-events/{eid}/entries",
                headers=h,
                json={"accounting_entry_id": attach_id, "relation_type": "primary"},
            )
            if attach.status_code in (200, 201):
                print(f"  关联分录 {attach_id}")
        # 推进到 collecting
        client.post(
            f"/api/economic-events/{eid}/transition",
            headers=h,
            json={"to_status": "collecting", "reason": "样例数据归集"},
        )

    # 尝试向量同步（Qdrant 不可用时忽略）
    sync = client.post("/api/economic-events/vector-sync?limit=20", headers=h)
    if sync.status_code == 200:
        print(f"向量同步: {sync.json()}")
    else:
        print(f"向量同步跳过: {sync.status_code}")

    print("")
    print("=== 样例账灌入完成 ===")
    print(f"BASE       : {BASE}")
    print(f"用户名     : {USERNAME}")
    print(f"密码       : {PASSWORD}")
    print(f"账簿 ID    : {ledger_id}")
    print(f"凭证 IDs   : {created_voucher_ids}")
    print(f"事件 IDs   : {event_ids}")
    print("前端建议   : 登录后切换到该账簿 → 凭证查询 / 经济事件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
