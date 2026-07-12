#!/usr/bin/env python3
"""通过 HTTP API 在生产容器内做序时簿导入端到端回归。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method: str, path: str, data: dict | None = None, token: str | None = None, form: dict | None = None):
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if form is not None:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        chunks: list[bytes] = []
        for name, (filename, content, ctype) in form.items():
            chunks.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
            )
            chunks.append(content)
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    phone = "13800000099"
    try:
        sms = req("POST", "/api/auth/sms/send", {"phone": phone})
    except urllib.error.HTTPError:
        phone = "13800000001"
        sms = req("POST", "/api/auth/sms/send", {"phone": phone})
    code = sms.get("code") or sms.get("dev_code") or "123456"
    login = req("POST", "/api/auth/sms/login", {"phone": phone, "code": code})
    token = login["access_token"]

    csv = (
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位\n"
        "记-001,2026-03-03,收到客户货款,1002,银行存款,12000,0,客户A\n"
        "记-001,2026-03-03,冲减应收账款,1122,应收账款,0,12000,客户A\n"
    ).encode("utf-8-sig")

    job = req(
        "POST",
        "/api/import-jobs",
        {"organization_name": "解析回归测试", "source_type": "ledger_day_book"},
        token=token,
    )
    job_id = job["id"]
    req(
        "POST",
        f"/api/import-jobs/{job_id}/files",
        form={"file": ("regression-daybook.csv", csv, "text/csv")},
        token=token,
    )
    result = req("POST", f"/api/import-jobs/{job_id}/process/sync", token=token)
    report = result.get("report") or {}
    entries = report.get("total_entries", 0)
    payload = {
        "job_id": job_id,
        "status": result.get("job", {}).get("status"),
        "total_entries": entries,
        "error_message": report.get("error_message"),
        "parse_diagnostics_engine": (report.get("parse_diagnostics") or {}).get("engine"),
        "failed_files": report.get("failed_files"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if entries > 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(1)
