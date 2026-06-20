import requests

# Process import job
url = "http://localhost:8000/api/import-jobs/1/process"
resp = requests.post(url)
print("Process status:", resp.status_code)
print(resp.json())

# List entries
entries_url = "http://localhost:8000/api/entries?import_job_id=1"
entries_resp = requests.get(entries_url)
print("\nEntries status:", entries_resp.status_code)
entries = entries_resp.json()
print(f"Total entries: {len(entries)}")
for e in entries:
    print(f"  ID={e['id']}, voucher_no={e['voucher_no']}, summary={e['summary']}, account={e['account_name']}, debit={e['debit_amount']}, credit={e['credit_amount']}")

# List risks
risks_url = "http://localhost:8000/api/risks?import_job_id=1"
risks_resp = requests.get(risks_url)
print("\nRisks status:", risks_resp.status_code)
risks = risks_resp.json()
print(f"Total risks: {len(risks)}")
for r in risks:
    print(f"  ID={r['id']}, type={r['risk_type']}, level={r['risk_level']}, title={r['title']}")
