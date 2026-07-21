#!/usr/bin/env python3
"""
fetch_durations_public.py
─────────────────────────
Complète les durées manquantes de catalogue.json sans aucune clé d'API.

Contrairement à fetch_durations.py (API Admin Cloudinary, qui exige
CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET), ce script lit la durée
directement dans l'en-tête du MP3 servi publiquement :

  1. une requête Range sur les 32 premiers Ko → tag ID3v2 + premiers frames
  2. Content-Range donne la taille totale du fichier
  3. Xing/Info (VBR) donne le nombre de frames → durée exacte
     sinon bitrate CBR + taille de la partie audio → durée

Aucun fichier n'est téléchargé en entier : ~32 à 64 Ko par titre.
Validé au format M:SS contre les durées déjà présentes dans catalogue.json.

Usage :
    python fetch_durations_public.py            # écrit catalogue.json
    python fetch_durations_public.py --dry-run  # n'écrit rien
"""

import argparse, json, math, struct, sys, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CATALOGUE = "catalogue.json"
CONCURRENCY = 12
RETRY = 3

BITRATES_V1L3 = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0]
BITRATES_V2L3 = [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0]
RATES = {3:[44100,48000,32000], 2:[22050,24000,16000], 0:[11025,12000,8000]}


def fetch(url, start, end):
    req = urllib.request.Request(url)
    req.add_header("Range", "bytes=%d-%d" % (start, end))
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read(), r.headers


def total_size(url, headers):
    cr = headers.get("Content-Range")
    if cr:
        return int(cr.split("/")[-1])
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=25) as r:
        return int(r.headers["Content-Length"])


def frame_header(buf, i):
    """(bitrate, samplerate, samples/frame, longueur du frame) ou None."""
    if i + 4 > len(buf) or buf[i] != 0xFF or (buf[i+1] & 0xE0) != 0xE0:
        return None
    b1, b2 = buf[i+1], buf[i+2]
    ver = (b1 >> 3) & 3        # 3 = MPEG1, 2 = MPEG2, 0 = MPEG2.5
    layer = (b1 >> 1) & 3      # 1 = Layer III
    if layer != 1 or ver == 1:
        return None
    bi, ri = (b2 >> 4) & 0xF, (b2 >> 2) & 3
    if bi in (0, 15) or ri == 3:
        return None
    br = (BITRATES_V1L3 if ver == 3 else BITRATES_V2L3)[bi] * 1000
    sr = RATES[ver][ri]
    pad = (b2 >> 1) & 1
    spf = 1152 if ver == 3 else 576
    return br, sr, spf, int(spf / 8 * br / sr) + pad


def wave_duration(buf, total):
    """Durée d'un flux RIFF/WAVE. Certains fichiers servis en .mp3 par
    Cloudinary contiennent en réalité du WAV : sans ce cas, le parseur MP3
    verrouille un faux sync et sort une durée absurde."""
    if buf[:4] != b"RIFF" or buf[8:12] != b"WAVE":
        return None
    pos, byte_rate = 12, None
    while pos + 8 <= len(buf):
        cid, size = buf[pos:pos+4], struct.unpack("<I", buf[pos+4:pos+8])[0]
        if cid == b"fmt " and pos + 16 <= len(buf):
            byte_rate = struct.unpack("<I", buf[pos+16:pos+20])[0]
        elif cid == b"data":
            if byte_rate:
                # size vaut 0 ou est tronqué sur les flux streamés : on
                # retombe alors sur la taille reelle du fichier.
                audio = size if 0 < size <= total else total - (pos + 8)
                return audio / byte_rate
            return None
        pos += 8 + size + (size & 1)
    return None


def probe(url):
    """Retourne la durée en secondes, ou lève une exception."""
    head, headers = fetch(url, 0, 32767)
    total = total_size(url, headers)

    off, base = 0, 0
    if head[:3] == b"ID3":
        sz = head[6:10]
        off = 10 + ((sz[0] & 0x7f) << 21 | (sz[1] & 0x7f) << 14
                    | (sz[2] & 0x7f) << 7 | (sz[3] & 0x7f))
        # Le tag ID3v2 pèse souvent des centaines de Ko (pochette embarquée) :
        # le premier frame audio est alors hors du bloc déjà téléchargé.
        # Fenetre confortable apres le tag : a 320 kbps un frame pese
        # ~1 Ko, il en faut plusieurs d'affilee pour valider le sync.
        if off > len(head) - 16384:
            head, _ = fetch(url, off, off + 32767)
            base, off = off, 0

    wav = wave_duration(head[off:], total - base - off)
    if wav:
        return wav

    for i in range(off, len(head) - 4):
        first = frame_header(head, i)
        if not first:
            continue
        # Un octet 0xFF suivi de bits de sync existe par hasard dans des
        # donnees non-MP3. On n'accepte le point de depart que si les frames
        # suivantes tombent exactement ou l'en-tete l'annonce.
        pos, chained = i, 0
        while chained < 4:
            nxt = frame_header(head, pos)
            if not nxt:
                break
            pos += nxt[3]
            if pos + 4 > len(head):
                break
            chained += 1
        if chained < 4:
            continue

        br, sr, spf, frame_len = first
        # Xing/Info : nombre de frames → durée exacte, y compris en VBR
        tag = head[i:i + frame_len + 4]
        for magic in (b"Xing", b"Info"):
            p = tag.find(magic)
            if p >= 0 and struct.unpack(">I", tag[p+4:p+8])[0] & 1:
                frames = struct.unpack(">I", tag[p+8:p+12])[0]
                if frames:
                    return frames * spf / sr

        # CBR : on retranche l'en-tête ID3, qui n'est pas de l'audio
        return (total - base - i) * 8 / br

    raise ValueError("aucun flux audio reconnu")


def secs_to_mmss(secs):
    s = int(math.floor(secs))
    return "%d:%02d" % (s // 60, s % 60)


# Garde-fou : le catalogue est fait d'illustrations sonores (mediane ~1min50,
# plus long titre connu 7min31). Au-dela, c'est un parsing qui a derape, pas un
# morceau : mieux vaut laisser la duree vide que d'afficher « 152:21 » sur une
# page indexee par Google.
MAX_PLAUSIBLE = 30 * 60


def one(track):
    for attempt in range(1, RETRY + 1):
        try:
            secs = probe(track["url"])
            if not 1 <= secs <= MAX_PLAUSIBLE:
                return track["id"], None
            return track["id"], secs_to_mmss(secs)
        except Exception:
            if attempt == RETRY:
                return track["id"], None
    return track["id"], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="sonde les titres mais n'écrit pas catalogue.json")
    args = ap.parse_args()

    with open(CATALOGUE, encoding="utf-8") as f:
        cat = json.load(f)

    # Les .mp4 de la playlist « samples » ne sont pas de l'audio : les sonder
    # ne produirait que du bruit, et ils sont exclus du build des pages.
    todo = [t for t in cat["tracks"]
            if (t.get("duration") or "") in ("", "0:00")
            and (t.get("url") or "").lower().endswith((".mp3", ".wav"))]
    print("%d titres sans durée → lecture des en-têtes MP3…\n" % len(todo))

    results, done, errors = {}, 0, 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(one, t) for t in todo]
        for fut in as_completed(futures):
            pid, mmss = fut.result()
            done += 1
            if mmss:
                results[pid] = mmss
            else:
                errors += 1
            if done % 100 == 0 or done == len(todo):
                print("  %d/%d  OK:%d  Err:%d" % (done, len(todo), len(results), errors),
                      flush=True)

    print("\n%d durées récupérées sur %d" % (len(results), len(todo)))
    if args.dry_run:
        print("--dry-run : catalogue.json inchangé")
        return

    updated = 0
    for t in cat["tracks"]:
        if t["id"] in results:
            t["duration"] = results[t["id"]]
            updated += 1

    # Meme mise en forme que fetch_catalogue.py, qui produit le fichier :
    # sans ca, completer quelques durees reecrit les 47 000 lignes du diff.
    with open(CATALOGUE, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=2)
    print("catalogue.json mis à jour : %d durées écrites ✓" % updated)


if __name__ == "__main__":
    main()
