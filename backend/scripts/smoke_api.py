"""端到端导入流程 API 联调脚本

流程：
1. POST /api/import-jobs
2. POST /api/import-jobs/{id}/files
3. POST /api/import-jobs/{id}/process
4. GET  /api/import-jobs/{id}
5. GET  /api/import-jobs/{id}/files
6. GET  /api/entries?import_job_id={id}
7. GET  /api/risks?import_job_id={id}
8. GET  /api/risks/{risk_id}
9. PATCH /api/risks/{risk_id}/review
10. PATCH /api/entries/{id}/tags
11. POST /api/entries/{id}/similar-search
"""
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
SAMPLE = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads" / "sample_voucher_2026.csv"


def step(label: str) -> None:
    print(f"\n=== {label} ===")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        step("1. 健康检查")
        r = client.get("/health")
        print("status", r.status_code, r.json())
        assert r.status_code == 200

        step("2. 创建导入任务")
        r = client.post("/api/import-jobs", json={
            "organization_name": "联调测试企业",
            "industry": "测试",
            "fiscal_year": 2026,
        })
        print("status", r.status_code, r.json())
        assert r.status_code == 200
        job = r.json()
        job_id = job["id"]
        assert job["status"] == "created"

        step("3. 上传 CSV 文件")
        with open(SAMPLE, "rb") as f:
            r = client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": (SAMPLE.name, f, "text/csv")},
            )
        print("status", r.status_code, r.json())
        assert r.status_code == 200
        file_info = r.json()

        step("4. 处理导入")
        r = client.post(f"/api/import-jobs/{job_id}/process")
        print("status", r.status_code, r.json())
        assert r.status_code == 200
        job = r.json()
        print("entry_count =", job["entry_count"], "status =", job["status"])
        assert job["entry_count"] > 0
        assert job["status"] == "completed"

        step("5. 查看任务文件")
        r = client.get(f"/api/import-jobs/{job_id}/files")
        print("status", r.status_code, r.json())
        assert r.status_code == 200
        assert any(item["id"] == file_info["id"] for item in r.json())

        step("6. 查询分录列表")
        r = client.get("/api/entries", params={"import_job_id": job_id})
        entries = r.json()
        print("status", r.status_code, "entry count =", len(entries))
        assert r.status_code == 200
        assert len(entries) == job["entry_count"]
        first_entry = entries[0]
        entry_id = first_entry["id"]

        step("7. 查询分录详情")
        r = client.get(f"/api/entries/{entry_id}")
        print("status", r.status_code, "voucher =", r.json().get("voucher_no"))
        assert r.status_code == 200

        step("8. 更新分录标签")
        r = client.patch(
            f"/api/entries/{entry_id}/tags",
            json={"tags": ["人工复核", "测试标签"]},
        )
        print("status", r.status_code, r.json())
        assert r.status_code == 200

        step("9. 分录标签列表")
        r = client.get(f"/api/entries/{entry_id}/tags")
        print("status", r.status_code, r.json())
        assert r.status_code == 200
        assert any(t["tag_name"] == "人工复核" for t in r.json())

        step("10. 查询风险列表")
        r = client.get("/api/risks", params={"import_job_id": job_id})
        risks = r.json()
        print("status", r.status_code, "risk count =", len(risks))
        assert r.status_code == 200
        assert len(risks) > 0, "应当至少产生一条风险"
        first_risk = risks[0]
        risk_id = first_risk["id"]

        step("11. 查询风险详情（含证据）")
        r = client.get(f"/api/risks/{risk_id}")
        detail = r.json()
        print("status", r.status_code, "title =", detail["title"], "evidence =", len(detail["evidence"]))
        assert r.status_code == 200
        assert "evidence" in detail
        assert isinstance(detail["evidence"], list)

        step("12. 复核风险（标记为已确认）")
        r = client.patch(
            f"/api/risks/{risk_id}/review",
            json={"action": "confirmed", "comment": "已人工核查，属于正常业务"},
        )
        print("status", r.status_code, "new status =", r.json()["status"])
        assert r.status_code == 200
        assert r.json()["status"] == "confirmed"

        step("13. 复核风险（标记为误报）")
        r = client.patch(
            f"/api/risks/{risks[1]['id']}/review",
            json={"action": "false_positive", "comment": "复核后判定为误报"},
        )
        print("status", r.status_code, "new status =", r.json()["status"])
        assert r.status_code == 200
        assert r.json()["status"] == "false_positive"

        step("14. 相似分录检索（向量库可能不可用）")
        r = client.post(f"/api/entries/{entry_id}/similar-search")
        body = r.json()
        print("status", r.status_code, "results =", len(body.get("results", [])), "msg =", body.get("message"))
        assert r.status_code == 200

        step("15. 风险类型统计")
        types: dict[str, int] = {}
        for risk in risks:
            t = risk["risk_type"]
            types[t] = types.get(t, 0) + 1
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

        step("16. 任务最终状态")
        r = client.get(f"/api/import-jobs/{job_id}")
        print("status", r.status_code, r.json())

    print("\n>>> 全部 API 联调通过 <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
