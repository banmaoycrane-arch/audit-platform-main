import requests
import json

BASE = "http://localhost:8000"

print("=== 1. Health Check ===")
resp = requests.get(f"{BASE}/health")
print(f"Status: {resp.status_code}")
print(f"Body: {resp.json()}")

print("\n=== 2. Create Import Job ===")
resp = requests.post(f"{BASE}/api/import-jobs", json={"organization_name": "测试企业"})
print(f"Status: {resp.status_code}")
job = resp.json()
print(f"Body: {job}")
job_id = job["id"]

print(f"\n=== 3. Upload File to Job {job_id} ===")
with open("test_data.csv", "rb") as f:
    files = {"file": ("test_data.csv", f, "text/csv")}
    resp = requests.post(f"{BASE}/api/import-jobs/{job_id}/files", files=files)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.json()}")

print(f"\n=== 4. Process Job {job_id} ===")
resp = requests.post(f"{BASE}/api/import-jobs/{job_id}/process")
print(f"Status: {resp.status_code}")
job = resp.json()
print(f"Body: {job}")

print(f"\n=== 5. List Entries (job_id={job_id}) ===")
resp = requests.get(f"{BASE}/api/entries", params={"import_job_id": job_id})
print(f"Status: {resp.status_code}")
entries = resp.json()
print(f"Total entries: {len(entries)}")
for e in entries:
    print(f"  ID={e['id']}, voucher_no={e['voucher_no']}, summary={e['summary']}, account={e['account_name']}, debit={e['debit_amount']}, credit={e['credit_amount']}, counterparty={e['counterparty']}")

print(f"\n=== 6. List Risks (job_id={job_id}) ===")
resp = requests.get(f"{BASE}/api/risks", params={"import_job_id": job_id})
print(f"Status: {resp.status_code}")
risks = resp.json()
print(f"Total risks: {len(risks)}")
for r in risks:
    print(f"  ID={r['id']}, type={r['risk_type']}, level={r['risk_level']}, title={r['title']}, confidence={r['confidence']}")

print("\n=== All tests completed ===")
