#!/usr/bin/env python3
"""
fetch_durations.py
──────────────────
Récupère la durée de chaque morceau via l'API Admin Cloudinary (ressource
individuelle + media_metadata=true) et met à jour catalogue.json.

BPM : déjà présent dans catalogue.json depuis fetch_catalogue.py.

Usage:
    pip install requests
    python fetch_durations.py
"""

import json, math, sys, time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.auth import HTTPBasicAuth

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DST_CLOUD  = "dtfm2cwm0"
DST_KEY    = "645955733157556"
DST_SECRET = "RB6VjSQe802PqJ7FA8cjQ-n0Qqg"

AUTH    = HTTPBasicAuth(DST_KEY, DST_SECRET)
API_URL = f"https://api.cloudinary.com/v1_1/{DST_CLOUD}/resources/video/upload"

CONCURRENCY = 10   # requêtes parallèles (conservateur)
RETRY       = 3

lock_print = threading.Lock()

def secs_to_mmss(secs: float) -> str:
    s = int(math.floor(secs))
    return f"{s // 60}:{s % 60:02d}"

def fetch_one(track: dict) -> tuple[str, str | None]:
    """Retourne (id, 'M:SS' | None)."""
    pid = track["id"]
    url = f"{API_URL}/{pid}"
    for attempt in range(1, RETRY + 1):
        try:
            r = requests.get(url, params={"media_metadata": "true"},
                             auth=AUTH, timeout=20)
            if r.status_code == 200:
                dur = r.json().get("duration")
                if dur is not None:
                    return pid, secs_to_mmss(float(dur))
                return pid, None
            if r.status_code in (420, 429):
                time.sleep(5 * attempt)
                continue
        except Exception:
            if attempt < RETRY:
                time.sleep(2)
    return pid, None

def main():
    with open("catalogue.json", encoding="utf-8") as f:
        cat = json.load(f)

    tracks_todo = [t for t in cat["tracks"] if not t.get("duration")]
    total       = len(tracks_todo)
    print(f"{total} morceaux sans durée → requêtes Cloudinary …\n")

    results: dict[str, str] = {}
    done    = 0
    errors  = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(fetch_one, t): t for t in tracks_todo}
        for fut in as_completed(futures):
            pid, mmss = fut.result()
            done += 1
            if mmss:
                results[pid] = mmss
            else:
                errors += 1
            if done % 50 == 0 or done == total:
                with lock_print:
                    print(f"  {done}/{total}  OK:{len(results)}  Err:{errors}", flush=True)

    print(f"\nRésultat : {len(results)} durées récupérées sur {total}")

    updated = 0
    for t in cat["tracks"]:
        if t["id"] in results:
            t["duration"] = results[t["id"]]
            updated += 1

    with open("catalogue.json", "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, separators=(",", ":"))

    print(f"catalogue.json mis à jour : {updated} durées écrites ✓")

if __name__ == "__main__":
    main()
