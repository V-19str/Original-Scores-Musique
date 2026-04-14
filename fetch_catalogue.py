import requests, json, re
from requests.auth import HTTPBasicAuth

CLOUD_NAME = "dqfogw7sg"
API_KEY    = "975546688173615"
API_SECRET = "Bgs1ukB5izJ9ilIxgIbt55F9eng"
auth = HTTPBasicAuth(API_KEY, API_SECRET)

# Récupérer tous les assets
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

# Récupérer les dossiers et leur contenu
folder_map = {}
r2 = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/folders", auth=auth)
folders = r2.json().get("folders", [])
print(f"Dossiers: {[f['name'] for f in folders]}")

for folder in folders:
    path = folder["path"]
    name = folder["name"]
    nc = None
    while True:
        params2 = {"resource_type": "video", "type": "upload", "max_results": 500, "prefix": path + "/"}
        if nc:
            params2["next_cursor"] = nc
        r3 = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/resources/video", params=params2, auth=auth)
        d3 = r3.json()
        for res in d3.get("resources", []):
            folder_map[res["public_id"]] = name
        nc = d3.get("next_cursor")
        if not nc:
            break
    print(f"  {name}: {len([v for v in folder_map.values() if v == name])} morceaux")

# Construire le catalogue
tracks = []
playlists = {}
for res in all_resources:
    public_id = res.get("public_id", "")
    url = res.get("secure_url", "")
    duration = round(res.get("duration", 0))
    filename = public_id.split("/")[-1]
    title = re.sub(r'[_-][a-z0-9]{6}$', '', filename, flags=re.I)
    title = title.replace("-", " ").replace("_", " ").title().strip()
    playlist = folder_map.get(public_id, "Divers")
    mins, secs = divmod(duration, 60)
    tracks.append({"id": public_id, "title": title, "playlist": playlist, "duration": f"{mins}:{secs:02d}", "url": url})
    playlists[playlist] = playlists.get(playlist, 0) + 1

tracks.sort(key=lambda t: (t["playlist"], t["title"]))
output = {"total": len(tracks), "playlists": sorted(playlists.keys()), "tracks": tracks}
with open("catalogue.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n✅ {len(tracks)} morceaux, {len(playlists)} playlists")
for p, c in sorted(playlists.items()):
    print(f"  {p}: {c}")
