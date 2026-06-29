#!/usr/bin/env python3
"""Seed a multi-ledger test account for manual + automated acceptance testing."""

from __future__ import annotations

import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
USERNAME = "test_runner_001"
PASSWORD = "testpass123"


def main() -> int:
    suffix = uuid.uuid4().hex[:6]
    client = httpx.Client(base_url=BASE, timeout=30)

    health = client.get("/health")
    if health.status_code != 200:
        print(f"后端未就绪: {BASE}")
        return 1

    # Register (ignore if exists)
    reg = client.post(
        "/api/auth/register",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    if reg.status_code not in (200, 400):
        print(f"注册失败: {reg.status_code} {reg.text}")
        return 1

    token = client.post(
        "/api/auth/login/password",
        json={"username": USERNAME, "password": PASSWORD},
    ).json().get("access_token")
    if not token:
        print("登录失败")
        return 1
    h = {"Authorization": f"Bearer {token}"}

    ledgers = client.get("/api/ledgers", headers=h).json()
    if len(ledgers) >= 2:
        print(f"账号 {USERNAME} 已存在，账簿数={len(ledgers)}，跳过创建")
        return 0

    team = client.post(
        "/api/teams",
        headers=h,
        json={"name": f"验收团队-{suffix}", "type": "company"},
    )
    if team.status_code != 200:
        print(f"创建团队失败: {team.text}")
        return 1
    team_id = team.json()["id"]

    ledger_names = ["2026山西尚德鑫", "新建账簿"]
    ledger_ids: list[int] = []
    for name in ledger_names:
        resp = client.post(
            "/api/ledgers",
            headers=h,
            json={"name": name, "team_id": team_id},
        )
        if resp.status_code != 200:
            print(f"创建账簿失败 {name}: {resp.text}")
            return 1
        ledger_ids.append(resp.json()["id"])

    for i, lid in enumerate(ledger_ids):
        client.post(f"/api/ledgers/{lid}/switch", headers=h)
        periods = client.post(
            "/api/accounting-periods",
            headers={**h, "X-Ledger-Id": str(lid)},
            json={
                "ledger_id": lid,
                "period_code": "2026-01",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )
        if periods.status_code != 200:
            print(f"创建期间失败: {periods.text}")
            return 1
        period = periods.json()
        amount = 11111 if i == 0 else 22222
        bulk = client.post(
            "/api/opening-balances/bulk",
            json={
                "organization_id": period["organization_id"],
                "period_id": period["id"],
                "ledger_id": lid,
                "items": [
                    {"account_code": "1002", "debit_balance": amount, "credit_balance": 0},
                    {"account_code": "2202", "debit_balance": 0, "credit_balance": amount},
                ],
            },
        )
        if bulk.status_code != 200:
            print(f"写入期初失败: {bulk.text}")
            return 1

    print("测试账号已就绪:")
    print(f"  用户名: {USERNAME}")
    print(f"  密码:   {PASSWORD}")
    print(f"  账簿:   {ledger_names[0]} (id={ledger_ids[0]}, 1002借方=11111)")
    print(f"          {ledger_names[1]} (id={ledger_ids[1]}, 1002借方=22222)")
    print("  页面:   http://127.0.0.1:5173/basic/opening-balances")
    return 0


if __name__ == "__main__":
    sys.exit(main())
