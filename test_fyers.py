import hashlib

import requests

api_key = "OM4OC4VU6O-100"
api_secret = "NJZSARNV1D"
auth_code = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiJPTTRPQzRWVTZPIiwidXVpZCI6IjMwNzU1ZmIyY2Q1ZTQyMmFiNWIyNWQ1MjY3ZDEzNGYzIiwiaXBBZGRyIjoiIiwibm9uY2UiOiIiLCJzY29wZSI6IiIsImRpc3BsYXlfbmFtZSI6IlhNMzczOTAiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiJiYWM2MTdiNzBkMDJhYzc2MmQ5NjQwNzUzOWFiMzNhM2MwMjE5Yjg2YWQ1NGVhMDQ1ODRhZjFhNCIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImF1ZCI6IltcImQ6MVwiLFwiZDoyXCIsXCJ4OjBcIixcIng6MVwiXSIsImV4cCI6MTc4MDE1NTY1NCwiaWF0IjoxNzgwMTI1NjU0LCJpc3MiOiJhcGkubG9naW4uZnllcnMuaW4iLCJuYmYiOjE3ODAxMjU2NTQsInN1YiI6ImF1dGhfY29kZSJ9.z99USTIyMUvxUalAE_V3IfH9NOSW6fiGORH8ttZ5l3o"

checksum = hashlib.sha256(f"{api_key}:{api_secret}".encode()).hexdigest()
payload = {
    "grant_type": "authorization_code",
    "appIdHash": checksum,
    "code": auth_code,
}

for prefix in ["api-t1", "api-t2"]:
    url = f"https://{prefix}.fyers.in/api/v3/validate-authcode"
    resp = requests.post(
        url, json=payload, headers={"Content-Type": "application/json"}
    )
    print(f"{prefix} response: {resp.status_code} {resp.text}")
