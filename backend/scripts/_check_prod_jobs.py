import json, ssl, urllib.request
CTX = ssl._create_unverified_context()
BASE = "https://47.122.117.76"
phone = "13800000001"

def req(method, path, data=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    with urllib.request.urlopen(r, context=CTX, timeout=60) as resp:
        return json.loads(resp.read())

sms = req("POST", "/api/auth/sms/code", {"phone": phone})
code = sms.get("code") or sms.get("sms_code") or "123456"
login = req("POST", "/api/auth/login/sms", {"phone": phone, "code": code})
token = login["access_token"]

for job_id in [9, 8, 7]:
    try:
        r = urllib.request.Request(
            BASE + f"/api/import-jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(r, context=CTX, timeout=60) as resp:
            job = json.loads(resp.read())
        print(f"job {job_id}:", json.dumps(job, ensure_ascii=False)[:800])
    except Exception as e:
        print(f"job {job_id}: error {e}")
