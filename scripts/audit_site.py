#!/usr/bin/env python3
"""
Audit du site Original Scores Music.

Trois contrôles :
  1. Intégrité de catalogue.json (JSON valide, champs url/title/playlist, aucun .wav)
  2. Les pages HTML publiques répondent en 200 sur https://osm-music.fr
  3. Toutes les URLs audio du catalogue sont joignables (Range bytes=0-4000)
     et ne sont pas de faux MP3 (en-tête RIFF/WAVE = fichier WAV déguisé)

Dépendances : bibliothèque standard Python uniquement.
Sortie : rapport lisible, code de sortie 1 si problème, 0 sinon.
"""

import argparse
import concurrent.futures
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Sortie UTF-8 quel que soit l'OS (console Windows cp1252 sinon en échec sur ✓/accents).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

BASE_URL = "https://osm-music.fr"

# Pages publiques du site (chemins relatifs à BASE_URL). "" = page d'accueil.
PUBLIC_PAGES = [
    "",
    "nouveautes.html",
    "television.html",
    "service.html",
    "qui-sommes-nous.html",
    "apropos.html",
    "aide.html",
    "inscription.html",
    "login-monteurs.html",
    "finaliser-inscription.html",
]

CATALOGUE = Path(__file__).resolve().parent.parent / "catalogue.json"
UA = "OSM-Audit/1.0 (+https://osm-music.fr)"


# ── HTTP helpers ─────────────────────────────────────────────────────────
def http_get(url, headers=None, timeout=20, max_bytes=None):
    """Requête GET. Renvoie (status, body_bytes). Lève sur erreur réseau."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = resp.getcode()
        body = resp.read(max_bytes) if max_bytes else resp.read()
        return status, body


# ── 1. Catalogue ─────────────────────────────────────────────────────────
def audit_catalogue():
    print("[1/3] Intégrité de catalogue.json")
    problems = []
    try:
        raw = CATALOGUE.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  ✗ Lecture impossible : {e}")
        return ["catalogue illisible"], []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON invalide : {e}")
        return ["catalogue JSON invalide"], []
    print("  ✓ JSON valide")

    tracks = data.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        print("  ✗ Champ 'tracks' absent ou vide")
        return ["catalogue sans pistes"], []

    missing_fields = 0
    wav_urls = []
    for i, t in enumerate(tracks):
        for field in ("url", "title", "playlist"):
            if not t.get(field):
                missing_fields += 1
                if len(problems) < 10:
                    problems.append(f"piste #{i} ({t.get('id', '?')}) : champ '{field}' manquant")
                break
        url = t.get("url", "")
        if isinstance(url, str) and url.lower().endswith(".wav"):
            wav_urls.append(t.get("id", url))

    print(f"  {'✓' if missing_fields == 0 else '✗'} {len(tracks)} pistes, "
          f"champs requis (url/title/playlist) : {len(tracks) - missing_fields} OK, "
          f"{missing_fields} en défaut")
    print(f"  {'✓' if not wav_urls else '✗'} URLs .wav : {len(wav_urls)}")
    if wav_urls:
        for w in wav_urls[:10]:
            print(f"      - {w}")

    if missing_fields:
        problems.append(f"{missing_fields} piste(s) avec champ manquant")
    if wav_urls:
        problems.append(f"{len(wav_urls)} URL(s) .wav dans le catalogue")
    return problems, tracks


# ── 2. Pages HTML ────────────────────────────────────────────────────────
def check_page(path):
    url = f"{BASE_URL}/{path}"
    try:
        status, _ = http_get(url, timeout=20, max_bytes=2048)
        return path, status, (status == 200)
    except urllib.error.HTTPError as e:
        return path, e.code, False
    except Exception as e:  # noqa: BLE001
        return path, f"ERR {type(e).__name__}", False


def audit_pages():
    print(f"\n[2/3] Pages HTML publiques ({len(PUBLIC_PAGES)})")
    problems = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(check_page, PUBLIC_PAGES))
    for path, status, ok in results:
        label = "/" + path
        print(f"  {'✓' if ok else '✗'} {str(status):>7}  {label}")
        if not ok:
            problems.append(f"page {label} → {status}")
    return problems


# ── 3. URLs audio ────────────────────────────────────────────────────────
def check_audio(track, timeout, retries=2):
    """Renvoie (id, status, problem) ; problem in {None,'injoignable','faux_mp3','page_erreur'}."""
    tid = track.get("id", "?")
    url = track.get("url", "")
    if not url:
        return tid, None, "injoignable"
    last = None
    for attempt in range(retries + 1):
        try:
            status, body = http_get(
                url, headers={"Range": "bytes=0-4000"}, timeout=timeout, max_bytes=4001
            )
            if status not in (200, 206):
                return tid, status, "injoignable"
            # Faux MP3 : conteneur WAV (RIFF....WAVE) servi sous une URL .mp3
            if body[:4] == b"RIFF" and body[8:12] == b"WAVE":
                return tid, status, "faux_mp3"
            # Page d'erreur HTML servie à la place du binaire
            head = body[:64].lstrip().lower()
            if head.startswith(b"<!doctype") or head.startswith(b"<html"):
                return tid, status, "page_erreur"
            return tid, status, None
        except urllib.error.HTTPError as e:
            last = e.code
            # 429/420/5xx : back-off puis nouvelle tentative
            if e.code in (420, 429) or e.code >= 500:
                time.sleep(1.5 * (attempt + 1))
                continue
            return tid, e.code, "injoignable"
        except Exception as e:  # noqa: BLE001
            last = f"ERR {type(e).__name__}"
            time.sleep(1.0 * (attempt + 1))
    return tid, last, "injoignable"


def audit_audio(tracks, workers, timeout, limit=None):
    subset = tracks[:limit] if limit else tracks
    print(f"\n[3/3] URLs audio ({len(subset)} pistes, {workers} threads, Range bytes=0-4000)")
    unreachable, fake, error_page = [], [], []
    done = 0
    total = len(subset)
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(check_audio, t, timeout): t for t in subset}
        for fut in concurrent.futures.as_completed(futs):
            tid, status, problem = fut.result()
            if problem == "injoignable":
                unreachable.append((tid, status))
            elif problem == "faux_mp3":
                fake.append((tid, status))
            elif problem == "page_erreur":
                error_page.append((tid, status))
            done += 1
            if done % 200 == 0 or done == total:
                el = time.time() - t0
                print(f"  … {done}/{total} testées ({el:.0f}s) — "
                      f"injoignables:{len(unreachable)} faux MP3:{len(fake)} pages erreur:{len(error_page)}")

    print(f"  {'✓' if not unreachable else '✗'} Injoignables : {len(unreachable)}")
    for tid, st in unreachable[:15]:
        print(f"      - {tid} → {st}")
    if len(unreachable) > 15:
        print(f"      … et {len(unreachable) - 15} autre(s)")
    print(f"  {'✓' if not fake else '✗'} Faux MP3 (RIFF/WAVE) : {len(fake)}")
    for tid, st in fake[:15]:
        print(f"      - {tid}")
    print(f"  {'✓' if not error_page else '✗'} Pages d'erreur servies : {len(error_page)}")
    for tid, st in error_page[:15]:
        print(f"      - {tid} → {st}")

    problems = []
    if unreachable:
        problems.append(f"{len(unreachable)} URL(s) audio injoignable(s)")
    if fake:
        problems.append(f"{len(fake)} faux MP3 (WAV déguisé)")
    if error_page:
        problems.append(f"{len(error_page)} URL(s) renvoyant une page HTML")
    return problems


# ── main ─────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Audit du site Original Scores Music")
    ap.add_argument("--workers", type=int, default=24, help="threads pour l'audit audio (défaut 24)")
    ap.add_argument("--timeout", type=int, default=20, help="timeout HTTP en secondes (défaut 20)")
    ap.add_argument("--limit", type=int, default=None, help="limiter le nombre d'URLs audio testées (debug)")
    ap.add_argument("--skip-audio", action="store_true", help="ne pas tester les URLs audio")
    ap.add_argument("--skip-pages", action="store_true", help="ne pas tester les pages HTML")
    args = ap.parse_args()

    print("=" * 60)
    print(" AUDIT ORIGINAL SCORES MUSIC")
    print("=" * 60)

    all_problems = []

    cat_problems, tracks = audit_catalogue()
    all_problems += cat_problems

    if not args.skip_pages:
        all_problems += audit_pages()

    if not args.skip_audio and tracks:
        all_problems += audit_audio(tracks, args.workers, args.timeout, args.limit)

    print("\n" + "=" * 60)
    if all_problems:
        print(f" RÉSULTAT : ÉCHEC — {len(all_problems)} problème(s)")
        for p in all_problems:
            print(f"   ✗ {p}")
        print("=" * 60)
        return 1
    print(" RÉSULTAT : SUCCÈS — aucun problème détecté")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
