import requests, json, re
from requests.auth import HTTPBasicAuth

CLOUD_NAME = "dqfogw7sg"
API_KEY    = "975546688173615"
API_SECRET = "Bgs1ukB5izJ9ilIxgIbt55F9eng"
auth = HTTPBasicAuth(API_KEY, API_SECRET)

PLAYLISTS = [
    "ACTION - POURSUITE - COMBAT - CHAOS - SPORT - EXTREME \u2013 URGENT",
    "ATMOSPHERE - GRANDS ESPACES - AERIEN - COSMIQUE \u2013 ABYSSAL",
    "BURLESQUE - HUMOUR - COMIQUE - THEATRAL - LEGER \u2013 COCASSE",
    "COUNTRY BLUES - DOBRO - BOOGIE-WOOGIE - GUITARE \u2013 USA",
    "ELECTRO - ELECTRONIQUE - BEAT - CLUBBING - DEEJAYING \u2013 PARTY",
    "ELECTRO - POP - ACTUEL - URBAIN - ARTY - ENERGIQUE \u2013 CORPORATE",
    "FOLK ACOUSTIQUE - ELECTRO ACOUSTIQUE - RELAX - GUITARE \u2013 HARMONY",
    "GROOVY - FUNKY - DISCO - RYTHMIQUE - GIMMICK - VIF \u2013 EVEILLE",
    "HARD ROCK - METAL - URGENT - RAGE - EXTREME - AGITATION \u2013 RAPIDE",
    "LATINO - AUSTRAL - MEXICAN - AMERIQUE DU SUD - CULTURE \u2013 WESTERN",
    "LOOPS - BOUCLE - LOOPING - BPM - METRONOME \u2013 ADAPTIVE",
    "LUDIQUE - ENFANTIN - DIVERTISSANT - THEATRAL - DROLE \u2013 AMUSANT",
    "NEUTRE - POSITIF \u2013 HAPPY",
    "NEUTRE- MELANCOLIE \u2013 TRISTESSE",
    "ORCHESTRAL - EPIQUE - SYMPHONIQUE - HARMONIE \u2013 HEROIQUE",
    "PANAME - PARIS - RETRO - ACCORDEON - PIGALLE \u2013 MONTMARTRE",
    "PARANORMAL - EXPERIMENTAL \u2013 HYPNOTIQUE",
    "PIANO - CLASSIQUE - INTIMISTE - CALME - MELANCOLIQUE - COSY \u2013 DOUX",
    "PIZZICATO - STACCATO - DRAMEDY - BETISIER - CARTOON \u2013 ANIMATION",
    "POP ACOUSTIQUE - SOFT - BALLADE - ACTUEL - ROAD \u2013 CHALEUREUX",
    "REGGAE - REGGATON - SKA - FUSION \u2013 JAMAICA",
    "ROCK - RIFFS - GUITARE - ELECTRIQUE - GARAGE - LIVE - ROCK N ROLL",
    "ROMANCE - MELANCOLIQUE - AMOUR - NOSTALGIE - TRISTESSE \u2013 DRAME",
    "SUSPENSE - INVESTIGATION - ENQUETE - ANGOISSE - ESPIONNAGE \u2013 POLICIER",
    "SWING - JAZZ - RYTHME - BIG BAND - JIVE \u2013 MANOUCHE",
    "TRANSITION - JINGLE - VIRGULE - PONCTUATION - RISE \u2013 WHOOSH",
    "URBAN - R&B - HIP HOP - STREET - ART - RAP \u2013 BEAT",
    "WORLD MUSIC - ETHNIQUE - CULTURE - METISSAGE - TRADITIONNEL",
]

LABELS = {
    "ACTION - POURSUITE - COMBAT - CHAOS - SPORT - EXTREME \u2013 URGENT": "Action",
    "ATMOSPHERE - GRANDS ESPACES - AERIEN - COSMIQUE \u2013 ABYSSAL": "Atmosph\u00e8re",
    "BURLESQUE - HUMOUR - COMIQUE - THEATRAL - LEGER \u2013 COCASSE": "Burlesque",
    "COUNTRY BLUES - DOBRO - BOOGIE-WOOGIE - GUITARE \u2013 USA": "Country Blues",
    "ELECTRO - ELECTRONIQUE - BEAT - CLUBBING - DEEJAYING \u2013 PARTY": "\u00c9lectro",
    "ELECTRO - POP - ACTUEL - URBAIN - ARTY - ENERGIQUE \u2013 CORPORATE": "\u00c9lectro-Pop",
    "FOLK ACOUSTIQUE - ELECTRO ACOUSTIQUE - RELAX - GUITARE \u2013 HARMONY": "Folk Acoustique",
    "GROOVY - FUNKY - DISCO - RYTHMIQUE - GIMMICK - VIF \u2013 EVEILLE": "Groovy",
    "HARD ROCK - METAL - URGENT - RAGE - EXTREME - AGITATION \u2013 RAPIDE": "Hard Rock",
    "LATINO - AUSTRAL - MEXICAN - AMERIQUE DU SUD - CULTURE \u2013 WESTERN": "Latino",
    "LOOPS - BOUCLE - LOOPING - BPM - METRONOME \u2013 ADAPTIVE": "Loops",
    "LUDIQUE - ENFANTIN - DIVERTISSANT - THEATRAL - DROLE \u2013 AMUSANT": "Ludique",
    "NEUTRE - POSITIF \u2013 HAPPY": "Neutre Positif",
    "NEUTRE- MELANCOLIE \u2013 TRISTESSE": "M\u00e9lancolie",
    "ORCHESTRAL - EPIQUE - SYMPHONIQUE - HARMONIE \u2013 HEROIQUE": "Orchestral",
    "PANAME - PARIS - RETRO - ACCORDEON - PIGALLE \u2013 MONTMARTRE": "Paname",
    "PARANORMAL - EXPERIMENTAL \u2013 HYPNOTIQUE": "Paranormal",
    "PIANO - CLASSIQUE - INTIMISTE - CALME - MELANCOLIQUE - COSY \u2013 DOUX": "Piano",
    "PIZZICATO - STACCATO - DRAMEDY - BETISIER - CARTOON \u2013 ANIMATION": "Pizzicato",
    "POP ACOUSTIQUE - SOFT - BALLADE - ACTUEL - ROAD \u2013 CHALEUREUX": "Pop Acoustique",
    "REGGAE - REGGATON - SKA - FUSION \u2013 JAMAICA": "Reggae",
    "ROCK - RIFFS - GUITARE - ELECTRIQUE - GARAGE - LIVE - ROCK N ROLL": "Rock",
    "ROMANCE - MELANCOLIQUE - AMOUR - NOSTALGIE - TRISTESSE \u2013 DRAME": "Romance",
    "SUSPENSE - INVESTIGATION - ENQUETE - ANGOISSE - ESPIONNAGE \u2013 POLICIER": "Suspense",
    "SWING - JAZZ - RYTHME - BIG BAND - JIVE \u2013 MANOUCHE": "Swing Jazz",
    "TRANSITION - JINGLE - VIRGULE - PONCTUATION - RISE \u2013 WHOOSH": "Transition",
    "URBAN - R&B - HIP HOP - STREET - ART - RAP \u2013 BEAT": "Urban",
    "WORLD MUSIC - ETHNIQUE - CULTURE - METISSAGE - TRADITIONNEL": "World Music",
}

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

# Mapper chaque morceau à sa playlist
folder_map = {}
for playlist_name in PLAYLISTS:
    nc = None
    count = 0
    while True:
        params2 = {"resource_type": "video", "type": "upload", "max_results": 500, "prefix": playlist_name + "/"}
        if nc:
            params2["next_cursor"] = nc
        r3 = requests.get(f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/resources/video", params=params2, auth=auth)
        d3 = r3.json()
        for res in d3.get("resources", []):
            folder_map[res["public_id"]] = LABELS.get(playlist_name, playlist_name)
            count += 1
        nc = d3.get("next_cursor")
        if not nc:
            break
    print(f"  {LABELS.get(playlist_name, playlist_name)}: {count} morceaux")

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
