import requests, json, re
from requests.auth import HTTPBasicAuth

CLOUD_NAME = "dqfogw7sg"
API_KEY    = "975546688173615"
API_SECRET = "Bgs1ukB5izJ9ilIxgIbt55F9eng"
auth = HTTPBasicAuth(API_KEY, API_SECRET)

all_resources = []
next_cursor = None
page = 1
while True:
    params = {"resource_type": "video", "type": "upload", "max_results": 500}
    if next_cursor:
        params["next_cursor"] = next_cursor
    r = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/resources/video", params=params, auth=auth)
    data = r.json()
    resources = data.get("resources", [])
    all_resources.extend(resources)
    print(f"Page {page}: {len(resources)} (total: {len(all_resources)})")
    next_cursor = data.get("next_cursor")
    page += 1
    if not next_cursor:
        break

# Lister les dossiers
r2 = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/folders", auth=auth)
folders_data = r2.json()
print("Dossiers:", json.dumps(folders_data, indent=2)[:2000])

folder_map = {}
for folder in folders_data.get("folders", []):
    path = folder["path"]
    fc = None
    while True:
        params2 = {"max_results": 500}
        if fc:
            params2["next_cursor"] = fc
        r3 = requests.get(
            f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/resources/video",
            params={**params2, "type": "upload", "prefix": path + "/"},
            auth=auth
        )
        d3 = r3.json()
        for res in d3.get("resources", []):
            folder_map[res["public_id"]] = path.split("/")[-1]
        fc = d3.get("next_cursor")
        if not fc:
            break
    print(f"Dossier {path}: {len([v for v in folder_map.values() if v == path.split('/')[-1]])}")

tracks = []
playlists = {}
for r in all_resources:
    public_id = r.get("public_id", "")
    url = r.get("secure_url", "")
    duration = round(r.get("duration", 0))
    filename = public_id.split("/")[-1]
    title = re.sub(r'[_-]([a-z0-9]{6})$', '', filename, flags=re.I).replace("-", " ").replace("_", " ").title().strip()
    playlist = folder_map.get(public_id, "Divers")
    mins, secs = divmod(duration, 60)
    tracks.append({"id": public_id, "title": title, "playlist": playlist, "duration": f"{mins}:{secs:02d}", "url": url})
    playlists[playlist] = playlists.get(playlist, 0) + 1

tracks.sort(key=lambda t: (t["playlist"], t["title"]))
output = {"total": len(tracks), "playlists": sorted(playlists.keys()), "tracks": tracks}
with open("catalogue.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"✅ {len(tracks)} morceaux, {len(playlists)} playlists")
for p, c in sorted(playlists.items()):
    print(f"  {p}: {c}")
