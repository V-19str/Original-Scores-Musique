#!/usr/bin/env python3
"""
Analyse audio automatique pour chaque morceau du catalogue OSM.
Détecte : énergie, tempo BPM, tonalité (majeur/mineur), fréquences dominantes.
Reprend là où il s'est arrêté si interrompu.
"""

import json, os, sys, time, requests, hashlib
import numpy as np
import librosa
from pathlib import Path

CATALOGUE_PATH = Path('catalogue.json')
PROGRESS_PATH  = Path('analysis_progress.json')
CACHE_DIR      = Path('/tmp/osm_audio_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SAVE_EVERY = 25   # sauvegarder catalogue.json tous les N morceaux
ANALYZE_SEC = 60  # analyser les N premières secondes (60s = bon équilibre vitesse/précision)

# ── Profils Krumhansl-Kessler pour la détection majeur/mineur ──────────────────
KK_MAJOR = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
KK_MINOR = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
NOTES     = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def detect_key_mode(y, sr):
    """Retourne ('majeur' ou 'mineur', note fondamentale)."""
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mean   = np.mean(chroma, axis=1)
    best_score, best_mode, best_note = -np.inf, 'majeur', 'C'
    for i in range(12):
        for profile, mode in [(KK_MAJOR,'majeur'),(KK_MINOR,'mineur')]:
            shifted = np.roll(profile, i)
            score   = np.corrcoef(mean, shifted)[0, 1]
            if score > best_score:
                best_score, best_mode, best_note = score, mode, NOTES[i]
    return best_mode, best_note

def detect_energy(y, sr):
    """Retourne 'calme', 'action' ou 'épique'."""
    rms      = float(np.mean(librosa.feature.rms(y=y)))
    contrast = float(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))
    if rms < 0.04:
        return 'calme'
    if rms > 0.10 and contrast > 22:
        return 'épique'
    return 'action'

def detect_tempo(y, sr):
    """Retourne (label, bpm)."""
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo)
    if bpm < 72:
        label = 'lent'
    elif bpm < 132:
        label = 'modéré'
    else:
        label = 'rapide'
    return label, round(bpm)

def detect_freq_profile(y, sr):
    """Retourne 'graves' (basse/percus) ou 'aigus' (cordes/piano)."""
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    if centroid < 1800:
        return 'graves'
    elif centroid > 3200:
        return 'aigus'
    return None  # médiums → on n'ajoute rien de trompeur

def download_cached(url, timeout=40):
    """Télécharge avec cache local sur /tmp."""
    fname = hashlib.md5(url.encode()).hexdigest() + '.mp3'
    fpath = CACHE_DIR / fname
    if fpath.exists():
        return fpath
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    fpath.write_bytes(r.content)
    return fpath

def analyze(url):
    """Lance l'analyse complète d'un fichier et retourne un dict de résultats."""
    fpath = download_cached(url)
    y, sr = librosa.load(str(fpath), duration=ANALYZE_SEC, sr=22050, mono=True)
    if len(y) < sr * 2:
        return None  # fichier trop court

    mode, note = detect_key_mode(y, sr)
    energy      = detect_energy(y, sr)
    tempo_lbl, bpm = detect_tempo(y, sr)
    freq        = detect_freq_profile(y, sr)

    new_tags = [mode, energy, tempo_lbl]
    if freq:
        new_tags.append(freq)
    return {'bpm': bpm, 'mode': mode, 'energy': energy, 'tempo': tempo_lbl, 'new_tags': new_tags}

def load_progress():
    if PROGRESS_PATH.exists():
        return set(json.loads(PROGRESS_PATH.read_text()))
    return set()

def save_progress(done_ids):
    PROGRESS_PATH.write_text(json.dumps(list(done_ids)))

# ── MAIN ───────────────────────────────────────────────────────────────────────
with open(CATALOGUE_PATH) as f:
    data = json.load(f)
tracks = data['tracks']

done = load_progress()
total  = len(tracks)
todo   = [t for t in tracks if t['id'] not in done]
print(f"📦 {total} morceaux — {len(done)} déjà analysés — {len(todo)} restants")

errors = []
saved_at = len(done)

for i, track in enumerate(todo):
    pct = ((len(done) + 1) / total) * 100
    print(f"[{len(done)+1}/{total}  {pct:.1f}%] {track['title']} ({track['playlist']})", end=' ', flush=True)

    try:
        result = analyze(track['url'])
        if result is None:
            print("⚠ trop court, ignoré")
        else:
            # Fusionner les nouveaux tags sans doublon
            existing = set(t.lower() for t in track.get('tags', []))
            for tag in result['new_tags']:
                if tag not in existing:
                    track.setdefault('tags', []).append(tag)
                    existing.add(tag)
            track['bpm'] = result['bpm']
            print(f"✓  bpm={result['bpm']} {result['energy']} {result['tempo']} {result['mode']}")
    except Exception as e:
        print(f"✗ erreur: {e}")
        errors.append({'id': track['id'], 'title': track['title'], 'error': str(e)})

    done.add(track['id'])
    save_progress(done)

    # Sauvegarde progressive
    if len(done) - saved_at >= SAVE_EVERY:
        data['tracks'] = tracks
        with open(CATALOGUE_PATH, 'w') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',',':'))
        saved_at = len(done)
        print(f"  💾 Sauvegarde intermédiaire ({len(done)}/{total})")

# Sauvegarde finale
data['tracks'] = tracks
with open(CATALOGUE_PATH, 'w') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',',':'))
PROGRESS_PATH.unlink(missing_ok=True)

print(f"\n✅ Analyse terminée. {len(done)} analysés, {len(errors)} erreurs.")
if errors:
    print("Erreurs :")
    for e in errors[:10]:
        print(f"  • {e['title']}: {e['error']}")
