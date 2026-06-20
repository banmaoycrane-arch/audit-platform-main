import requests

# Upload file using Python requests (proper encoding)
url = "http://localhost:8000/api/import-jobs/1/files"
with open("test_data.csv", "rb") as f:
    files = {"file": ("test_data.csv", f, "text/csv")}
    resp = requests.post(url, files=files)
    print(resp.status_code)
    print(resp.json())
