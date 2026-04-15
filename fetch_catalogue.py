import requests, json, re
from requests.auth import HTTPBasicAuth

CLOUD_NAME = "dqfogw7sg"
API_KEY    = "975546688173615"
API_SECRET = "Bgs1ukB5izJ9ilIxgIbt55F9eng"
auth = HTTPBasicAuth(API_KEY, API_SECRET)

LABELS = {
    "ACTION - POURSUITE - COMBAT - CHAOS - SPORT - EXTREME - URGENT": "Action",
    "ATMOSPHERE - GRANDS ESPACES - AERIEN - COSMIQUE - ABYSSAL": "Atmosphère",
    "BURLESQUE - HUMOUR - COMIQUE - THEATRAL - LEGER - COCASSE": "Burlesque",
    "COUNTRY BLUES - DOBRO - BOOGIE-WOOGIE - GUITARE - USA": "Country Blues",
    "ELECTRO - ELECTRONIQUE - BEAT - CLUBBING - DEEJAYING - PARTY": "Électro",
    "ELECTRO - POP - ACTUEL - URBAIN - ARTY - ENERGIQUE - CORPORATE": "Électro-Pop",
    "FOLK ACOUSTIQUE - ELECTRO ACOUSTIQUE - RELAX - GUITARE - HARMONY": "Folk Acoustique",
    "GROOVY - FUNKY - DISCO - RYTHMIQUE - GIMMICK - VIF - EVEILLE": "Groovy",
    "HARD ROCK - METAL - URGENT - RAGE - EXTREME - AGITATION - RAPIDE": "Hard Rock",
    "LATINO - AUSTRAL - MEXICAN - AMERIQUE DU SUD - CULTURE - WESTERN": "Latino",
    "LOOPS - BOUCLE - LOOPING - BPM - METRONOME - ADAPTIVE": "Loops",
    "LUDIQUE - ENFANTIN - DIVERTISSANT - THEATRAL - DROLE - AMUSANT": "Ludique",
    "NEUTRE - POSITIF - HAPPY": "Neutre Positif",
    "NEUTRE- MELANCOLIE - TRISTESSE": "Mélancolie",
    "ORCHESTRAL - EPIQUE - SYMPHONIQUE - HARMONIE - HEROIQUE": "Orchestral",
    "PANAME - PARIS - RETRO - ACCORDEON - PIGALLE - MONTMARTRE": "Paname",
    "PARANORMAL - EXPERIMENTAL - HYPNOTIQUE": "Paranormal",
    "PIANO - CLASSIQUE - INTIMISTE - CALME - MELANCOLIQUE - COSY - DOUX": "Piano",
    "PIZZICATO - STACCATO - DRAMEDY - BETISIER - CARTOON - ANIMATION": "Pizzicato",
    "POP ACOUSTIQUE - SOFT - BALLADE - ACTUEL - ROAD - CHALEUREUX": "Pop Acoustique",
    "REGGAE - REGGATON - SKA - FUSION - JAMAICA": "Reggae",
    "ROCK - RIFFS - GUITARE - ELECTRIQUE - GARAGE - LIVE - ROCK N ROLL": "Rock",
    "ROMANCE - MELANCOLIQUE - AMOUR - NOSTALGIE - TRISTESSE - DRAME": "Romance",
    "SUSPENSE - INVESTIGATION - ENQUETE - ANGOISSE - ESPIONNAGE - POLICIER": "Suspense",
    "SWING - JAZZ - RYTHME - BIG BAND - JIVE - MANOUCHE": "Swing Jazz",
    "TRANSITION - JINGLE - VIRGULE - PONCTUATION - RISE - WHOOSH": "Transition",
    "URBAN - R&B - HIP HOP - STREET - ART - RAP - BEAT": "Urban",
    "WORLD MUSIC - ETHNIQUE - CULTURE - METISSAGE - TRADITIONNEL": "World Music",
}

PREFIX = "ORIGINAL SCORES MUSIC - COLLECTIONS - LQ MP3/"

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

tracks = []
playlists = {}
for res in all_resources:
    public_id = res.get("public_id", "")
    url = res.get("secure_url", "")
    duration  = res.get("duration") or 0
    duration  = round(float(duration)) if duration else 0
    asset_folder = res.get("asset_folder", "")
    display_name = res.get("display_name", "")
    
    # Extraire le nom du sous-dossier
    if asset_folder.startswith(PREFIX):
        folder_name = asset_folder[len(PREFIX):]
    else:
        folder_name = asset_folder
    
    playlist = LABELS.get(folder_name, folder_name if folder_name else "Divers")
    
    # Titre depuis display_name
    title = display_name or public_id.split("/")[-1]
    title = re.sub(r'[_-][a-z0-9]{6}$', '', title, flags=re.I)
    title = title.replace("-", " ").replace("_", " ").title().strip()
    
    mins, secs = divmod(duration, 60)
    tracks.append({"id": public_id, "title": title, "playlist": playlist, "duration": f"{mins}:{secs:02d}" if duration > 0 else "", "url": url})
    playlists[playlist] = playlists.get(playlist, 0) + 1

tracks.sort(key=lambda t: (t["playlist"], t["title"]))
output = {"total": len(tracks), "playlists": sorted(playlists.keys()), "tracks": tracks}
with open("catalogue.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n✅ {len(tracks)} morceaux, {len(playlists)} playlists")
for p, c in sorted(playlists.items()):
    print(f"  {p}: {c}")
