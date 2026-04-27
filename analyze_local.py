#!/usr/bin/env python3
"""
OSM — Analyse audio automatique
Tourne sur ton PC, télécharge chaque morceau depuis Cloudinary,
détecte énergie / tempo / tonalité / fréquences et met à jour catalogue.json
"""

import json, os, hashlib, time, sys
from pathlib import Path

try:
    import requests
    import numpy as np
    import librosa
except ImportError:
    print("❌ Dépendances manquantes. Lance d'abord install_et_lancer.bat")
    input("Appuie sur Entrée pour quitter...")
    sys.exit(1)

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
CATALOGUE   = BASE / 'catalogue.json'
PROGRESS    = BASE / 'analysis_progress.json'
CACHE_DIR   = BASE / '_audio_cache'
CACHE_DIR.mkdir(exist_ok=True)

SAVE_EVERY  = 30    # sauvegarde catalogue.json tous les N morceaux
ANALYZE_SEC = 45    # analyser les N premières secondes par morceau

# ── Profils Krumhansl-Kessler (détection majeur/mineur) ──────────────────────
KK_MAJOR = [6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]
KK_MINOR = [6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17]

def detect_mode(y, sr):
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mean   = np.mean(chroma, axis=1)
    best, mode = -9, 'majeur'
    for i in range(12):
        for profile, label in [(KK_MAJOR,'majeur'),(KK_MINOR,'mineur')]:
            score = float(np.corrcoef(mean, np.roll(profile, i))[0,1])
            if score > best:
                best, mode = score, label
    return mode

def detect_energy(y, sr):
    rms      = float(np.mean(librosa.feature.rms(y=y)))
    contrast = float(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))
    if rms < 0.04:
        return 'calme'
    if rms > 0.10 and contrast > 22:
        return 'épique'
    return 'action'

def detect_tempo(y, sr):
    bpm = float(librosa.beat.beat_track(y=y, sr=sr)[0])
    if bpm < 72:   return 'lent',   round(bpm)
    if bpm < 132:  return 'modéré', round(bpm)
    return 'rapide', round(bpm)

def detect_freq(y, sr):
    c = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    if c < 1800: return 'graves'
    if c > 3200: return 'aigus'
    return None

def download(url):
    fname = CACHE_DIR / (hashlib.md5(url.encode()).hexdigest() + '.mp3')
    if fname.exists():
        return fname
    r = requests.get(url, timeout=60, headers={'User-Agent':'Mozilla/5.0'})
    r.raise_for_status()
    fname.write_bytes(r.content)
    return fname

def analyze(url):
    path = download(url)
    y, sr = librosa.load(str(path), duration=ANALYZE_SEC, sr=22050, mono=True)
    if len(y) < sr * 2:
        return None
    mode           = detect_mode(y, sr)
    energy         = detect_energy(y, sr)
    tempo_lbl, bpm = detect_tempo(y, sr)
    freq           = detect_freq(y, sr)
    new_tags = [mode, energy, tempo_lbl]
    if freq: new_tags.append(freq)
    return {'bpm': bpm, 'mode': mode, 'energy': energy, 'tempo': tempo_lbl, 'new_tags': new_tags}

# ── Chargement ────────────────────────────────────────────────────────────────
with open(CATALOGUE, encoding='utf-8') as f:
    data = json.load(f)
tracks = data['tracks']

done = set(json.loads(PROGRESS.read_text())) if PROGRESS.exists() else set()
todo = [t for t in tracks if t['id'] not in done]

print(f"\n🎵 OSM — Analyse audio automatique")
print(f"   {len(tracks)} morceaux · {len(done)} déjà faits · {len(todo)} restants")
print(f"   Cache : {CACHE_DIR}")
print(f"   Durée estimée : ~{len(todo)//60 + 1}h{len(todo)%60:02d}min\n")

errors   = []
saved_at = len(done)

for track in todo:
    pct  = (len(done)+1) / len(tracks) * 100
    line = f"[{len(done)+1}/{len(tracks)}  {pct:.1f}%]  {track['title'][:45]:<45}"
    print(line, end=' ', flush=True)
    try:
        r = analyze(track['url'])
        if r is None:
            print("⚠  trop court")
        else:
            existing = {t.lower() for t in track.get('tags', [])}
            for tag in r['new_tags']:
                if tag not in existing:
                    track.setdefault('tags', []).append(tag)
            track['bpm'] = r['bpm']
            print(f"✓  {r['bpm']}bpm  {r['energy']:<8} {r['tempo']:<8} {r['mode']}")
    except Exception as e:
        msg = str(e)[:60]
        print(f"✗  {msg}")
        errors.append({'title': track['title'], 'error': msg})

    done.add(track['id'])
    PROGRESS.write_text(json.dumps(list(done)))

    if len(done) - saved_at >= SAVE_EVERY:
        data['tracks'] = tracks
        with open(CATALOGUE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',',':'))
        saved_at = len(done)
        print(f"\n   💾  Sauvegarde — {len(done)}/{len(tracks)} faits\n")

# Sauvegarde finale
data['tracks'] = tracks
with open(CATALOGUE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',',':'))
PROGRESS.unlink(missing_ok=True)

print(f"\n✅  Terminé ! {len(done)} analysés, {len(errors)} erreurs.")
if errors:
    print("Erreurs :")
    for e in errors[:10]:
        print(f"  • {e['title']}: {e['error']}")

# Nettoyer le cache si tout OK
if not errors:
    import shutil
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    print("🗑  Cache audio supprimé.")

input("\nAppuie sur Entrée pour fermer...")
