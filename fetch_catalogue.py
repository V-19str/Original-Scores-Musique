import requests, json, re, urllib.parse
from requests.auth import HTTPBasicAuth

CLOUD_NAME = "dqfogw7sg"
API_KEY    = "975546688173615"
API_SECRET = "Bgs1ukB5izJ9ilIxgIbt55F9eng"
auth = HTTPBasicAuth(API_KEY, API_SECRET)

print("=== DOSSIERS RACINE ===")
r = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/folders", auth=auth)
data = r.json()
folders = data.get("folders", [])
for f in folders:
    print(f"  path={f.get('path')} name={f.get('name')}")

print("\n=== SOUS-DOSSIERS ===")
for folder in folders:
    path = folder.get("path", "")
    encoded = urllib.parse.quote(path, safe="")
    r2 = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/folders/{encoded}", auth=auth)
    sub = r2.json()
    subs = sub.get("folders", [])
    if subs:
        print(f"\n'{path}' contient {len(subs)} sous-dossiers:")
        for s in subs[:5]:
            print(f"    {s.get('path')} / {s.get('name')}")

print("\n=== PREMIER ASSET ===")
r3 = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/resources/video?max_results=1&type=upload", auth=auth)
d3 = r3.json()
if d3.get("resources"):
    res = d3["resources"][0]
    print(json.dumps(res, indent=2, ensure_ascii=False))
