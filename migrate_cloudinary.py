#!/usr/bin/env python3
"""
migrate_cloudinary.py
─────────────────────
Copie les playlists Action, Suspense, Piano, Orchestral et Groovy
du compte Cloudinary source (dqfogw7sg) vers le compte destination (dfm2cwm0),
puis met à jour catalogue.json pour que ces pistes pointent vers le nouveau cloud.

Usage :
    pip install requests
    python migrate_cloudinary.py

En cas d'interruption, relancez le script : la progression est sauvegardée dans
migration_progress.json et les pistes déjà migrées sont ignorées.
"""

import hashlib
import json
import time
import requests
from pathlib import Path

# ── Compte source (lecture seule) ───────────────────────────────────────────
SRC_CLOUD  = "dqfogw7sg"
SRC_KEY    = "968571581867276"
SRC_SECRET = "4O-X2gHhbCCud7Yppkpe38TxhTc"

# ── Compte destination ───────────────────────────────────────────────────────
DST_CLOUD  = "dfm2cwm0"
DST_KEY    = ""   # ← remplir avec la clé API du nouveau compte
DST_SECRET = ""   # ← remplir avec le secret API du nouveau compte

# ── Playlists à migrer ───────────────────────────────────────────────────────
PLAYLISTS_TO_MIGRATE = {"Action", "Suspense", "Piano", "Orchestral", "Groovy"}

CATALOGUE_PATH = Path("catalogue.json")
PROGRESS_PATH  = Path("migration_progress.json")

# Cloudinary free tier : ~500 requêtes/heure → 1 req toutes les ~0.5 s est sûr
SLEEP_BETWEEN_UPLOADS = 0.5   # secondes
MAX_RETRIES = 3
RETRY_DELAY = 5               # secondes entre deux tentatives


def sign(params: dict, secret: str) -> str:
    """
    Calcule la signature Cloudinary (SHA-1) pour un dict de paramètres.
    Exclut les champs qui ne doivent pas être signés.
    """
    excluded = {"file", "api_key", "resource_type", "signature", "cloud_name"}
    parts = "&".join(
        f"{k}={v}"
        for k, v in sorted(params.items())
        if k not in excluded
    )
    return hashlib.sha1((parts + secret).encode()).hexdigest()


def upload_track(track: dict) -> str | None:
    """
    Upload un fichier vers le compte destination en passant l'URL source.
    Retourne la nouvelle secure_url, ou None après MAX_RETRIES tentatives.
    """
    url = f"https://api.cloudinary.com/v1_1/{DST_CLOUD}/video/upload"
    ts  = int(time.time())

    signed_params = {
        "public_id": track["id"],
        "overwrite": "true",
        "timestamp": ts,
    }
    signature = sign(signed_params, DST_SECRET)

    data = {
        **signed_params,
        "file":      track["url"],    # Cloudinary télécharge depuis l'URL source
        "api_key":   DST_KEY,
        "signature": signature,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(url, data=data, timeout=120)
            if r.status_code == 200:
                return r.json().get("secure_url")
            # 420 / 429 = rate limit
            if r.status_code in (420, 429):
                wait = RETRY_DELAY * attempt * 4
                print(f"\n  ⏳ Rate limit (tentative {attempt}) — attente {wait}s", flush=True)
                time.sleep(wait)
                continue
            print(f"\n  ✗ HTTP {r.status_code} : {r.text[:300]}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
        except requests.exceptions.Timeout:
            print(f"\n  ✗ Timeout (tentative {attempt})")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"\n  ✗ Erreur : {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return None


def patch_url(old_url: str, new_secure_url: str) -> str:
    """Retourne new_secure_url (l'URL renvoyée par Cloudinary est déjà correcte)."""
    return new_secure_url


def main() -> None:
    # ── Vérifications préalables ─────────────────────────────────────────────
    if not DST_KEY or not DST_SECRET:
        print("❌  Remplis DST_KEY et DST_SECRET dans le script avant de lancer.")
        return

    if not CATALOGUE_PATH.exists():
        print(f"❌  {CATALOGUE_PATH} introuvable.")
        return

    # ── Chargement du catalogue ──────────────────────────────────────────────
    catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    tracks    = catalogue["tracks"]

    # ── Chargement de la progression précédente ──────────────────────────────
    progress: dict[str, str] = {}
    if PROGRESS_PATH.exists():
        progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        print(f"↩  Reprise : {len(progress)} piste(s) déjà migrée(s)\n")

    # ── Sélection des pistes cibles ──────────────────────────────────────────
    targets = [t for t in tracks if t["playlist"] in PLAYLISTS_TO_MIGRATE]
    by_playlist = {}
    for t in targets:
        by_playlist.setdefault(t["playlist"], 0)
        by_playlist[t["playlist"]] += 1

    print(f"📦  {len(targets)} pistes à migrer vers « {DST_CLOUD} »")
    for pl, n in sorted(by_playlist.items()):
        print(f"     {pl}: {n}")
    print()

    # ── Migration ────────────────────────────────────────────────────────────
    migrated = 0
    skipped  = 0
    failed   = []

    for i, track in enumerate(targets, 1):
        tid = track["id"]

        # Déjà migré lors d'une session précédente
        if tid in progress:
            track["url"] = progress[tid]
            migrated += 1
            skipped  += 1
            continue

        label = f"[{i:>3}/{len(targets)}] {track['playlist']:<12} · {track['title']}"
        print(f"{label}", end=" … ", flush=True)

        new_url = upload_track(track)

        if new_url:
            progress[tid] = new_url
            track["url"]  = new_url
            migrated += 1
            print("✓")
            # Sauvegarde après chaque upload réussi (reprise possible)
            PROGRESS_PATH.write_text(
                json.dumps(progress, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        else:
            failed.append(f"{track['playlist']} · {track['title']}")
            print("⚠  échec (URL source conservée)")

        time.sleep(SLEEP_BETWEEN_UPLOADS)

    # ── Mise à jour de catalogue.json ────────────────────────────────────────
    CATALOGUE_PATH.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # ── Résumé ───────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    newly = migrated - skipped
    print(f"✅  {newly} nouvelles pistes migrées  |  {skipped} déjà faites  |  {len(failed)} échec(s)")
    if failed:
        print(f"\n⚠  Pistes en échec (URL source conservée) :")
        for f in failed:
            print(f"   · {f}")
    print(f"\n📄  catalogue.json mis à jour")
    if migrated == len(targets) and not failed:
        if PROGRESS_PATH.exists():
            PROGRESS_PATH.unlink()
            print(f"🗑  migration_progress.json supprimé")

    # ── Vérification rapide ──────────────────────────────────────────────────
    new_cloud_count = sum(
        1 for t in tracks
        if t["playlist"] in PLAYLISTS_TO_MIGRATE and DST_CLOUD in t.get("url", "")
    )
    print(f"\n🔍  {new_cloud_count}/{len(targets)} URLs pointent maintenant vers « {DST_CLOUD} »")


if __name__ == "__main__":
    main()
