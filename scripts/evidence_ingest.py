#!/usr/bin/env python3
"""证据云空间 Ingest CLI — 企业自建推送示例。

用法：
  export TOKEN="<登录后获取的 JWT>"
  python scripts/evidence_ingest.py --ledger-id 1 --file ./invoice.pdf --file-type invoice

也可指定 API 地址：
  python scripts/evidence_ingest.py --base-url http://127.0.0.1:8000 --token $TOKEN ...
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="向证据云空间收件箱推送文件")
    parser.add_argument("--base-url", default=os.environ.get("AUDIT_API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("TOKEN") or os.environ.get("AUDIT_TOKEN"))
    parser.add_argument("--ledger-id", type=int, required=True, help="目标账簿 ID")
    parser.add_argument("--file", required=True, help="要上传的文件路径")
    parser.add_argument("--file-type", default=None, help="可选：invoice/contract/statement/other")
    args = parser.parse_args()

    if not args.token:
        print("错误：请通过 --token 或环境变量 TOKEN 提供 JWT", file=sys.stderr)
        return 2

    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"错误：文件不存在 {file_path}", file=sys.stderr)
        return 2

    url = f"{args.base_url.rstrip('/')}/api/files/ingest"
    mime, _ = mimetypes.guess_type(str(file_path))
    headers = {
        "Authorization": f"Bearer {args.token}",
        "X-Ingest-Channel": "cli",
    }
    data = {"ledger_id": str(args.ledger_id)}
    if args.file_type:
        data["file_type"] = args.file_type

    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle, mime or "application/octet-stream")}
        response = requests.post(url, headers=headers, data=data, files=files, timeout=120)

    if response.status_code >= 400:
        print(f"上传失败 HTTP {response.status_code}: {response.text}", file=sys.stderr)
        return 1

    payload = response.json()
    file_id = payload.get("id")
    print(f"已落入收件箱：file_id={file_id} filename={payload.get('filename')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
