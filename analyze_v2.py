#!/usr/bin/env python3
"""
OSM — Analyse audio v2
Ajoute aux tags existants : tonalité précise, vocal/instrumental, genre, instruments, usage.
Aucune nouvelle dépendance — utilise uniquement librosa (déjà installé).
Compatible Windows · Tourne en tâche de fond · Reprend là où il s'est arrêté.
"""

import json, hashlib, sys, concurrent.futures
from pathlib import Path

try:
    import requests
    import numpy as np
    import librosa
except ImportError:
    print("❌ Dépendances manquantes : pip install librosa requests numpy")
    input("Appuie sur Entrée pour quitter...")
    sys.exit(1)

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent
CATALOGUE  = BASE / 'catalogue.json'
PROGRESS   = BASE / 'analysis_v2_progress.json'
CACHE_DIR  = BASE / '_audio_cache'
CACHE_DIR.mkdir(exist_ok=True)

SAVE_EVERY  = 20
ANALYZE_SEC = 60  # 60s pour mieux capter genre et instruments

# ── Marqueurs v2 (sert à détecter si un morceau est déjà traité) ──────────────
V2_MARKERS = {
    'orchestral','électronique','acoustique','jazz','ambient','hybride',
    'vocal','instrumental',
    'piano','cordes','cuivres','guitare','percussions','basse','synthétiseur',
    'cinéma','publicité','documentaire',
}

# ── Tonalités ─────────────────────────────────────────────────────────────────
NOTE_NAMES = ['do','do#','ré','ré#','mi','fa','fa#','sol','sol#','la','la#','si']
KK_MAJOR   = [6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]
KK_MINOR   = [6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17]

def _f(x):
    return float(np.asarray(x).flat[0])

# ── Détections ────────────────────────────────────────────────────────────────

def detect_key(y, sr):
    """Retourne la tonalité précise parmi 24 clés : 'ré# mineur', 'sol majeur'…"""
    chroma     = librosa.feature.chroma_cqt(y=y, sr=sr)
    mean_chroma = np.mean(chroma, axis=1)
    best_score, best_key = -9, 'do majeur'
    for i in range(12):
        for profile, suffix in [(KK_MAJOR,'majeur'), (KK_MINOR,'mineur')]:
            score = _f(np.corrcoef(mean_chroma, np.roll(profile, i))[0, 1])
            if score > best_score:
                best_score = score
                best_key   = f"{NOTE_NAMES[i]} {suffix}"
    return best_key


def detect_vocal(y, sr):
    """Catalogue OSM = 100% instrumental."""
    return 'instrumental'


def detect_genre(y, sr, tempo, zcr, centroid, contrast, onset):
    """Détecte le genre : orchestral, électronique, acoustique, jazz, ambient, hybride."""
    rms = _f(np.mean(librosa.feature.rms(y=y)))

    # Ambient : peu de transients, énergie globale basse
    if onset < 0.25 and rms < 0.04:
        return 'ambient'

    # Électronique : tempo fort + centroïde élevé + rythme régulier
    _, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_reg = float(np.std(np.diff(beats))) if len(beats) > 2 else 999
    if tempo > 105 and centroid > 3200 and beat_reg < 6:
        return 'électronique'

    # Orchestral : fort contraste spectral, ZCR bas
    if contrast > 18 and zcr < 0.09 and centroid < 4200:
        return 'orchestral'

    # Jazz : chromas complexes, tempo modéré
    chroma     = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_var = _f(np.mean(np.var(chroma, axis=1)))
    if chroma_var > 0.038 and 55 < tempo < 175 and zcr < 0.13:
        return 'jazz'

    # Acoustique : centroïde bas, ZCR bas
    if centroid < 2800 and zcr < 0.11:
        return 'acoustique'

    return 'hybride'


def detect_instruments(y, sr, centroid, zcr, onset, genre):
    """Retourne 1 à 2 instruments dominants."""
    instruments = []

    harm, perc = librosa.effects.hpss(y)
    total = max(_f(np.mean(np.abs(y))), 1e-6)
    perc_ratio = _f(np.mean(np.abs(perc))) / total
    harm_ratio = _f(np.mean(np.abs(harm))) / total

    # Énergie par bande de fréquence
    S     = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    low_e = _f(np.mean(S[freqs < 300]))
    mid_e = _f(np.mean(S[(freqs >= 300) & (freqs < 2000)]))

    mfcc       = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=6)
    mfcc_range = _f(np.std(mfcc[0]))

    # Percussions
    if perc_ratio > 0.32 and onset > 0.45:
        instruments.append('percussions')

    # Cordes : ZCR très bas, milieu dominant, harmonique fort
    if zcr < 0.065 and mid_e > low_e * 0.8 and harm_ratio > 0.45 and centroid < 3200:
        instruments.append('cordes')

    # Piano : transients + large couverture spectrale
    if onset > 0.55 and mfcc_range > 22 and perc_ratio < 0.45 and 'cordes' not in instruments:
        instruments.append('piano')

    # Cuivres : centroïde élevé, milieu fort
    if centroid > 2600 and mid_e > low_e * 1.4 and harm_ratio > 0.35 and 'cordes' not in instruments:
        instruments.append('cuivres')

    # Guitare : fréquences mi, transients modérés, pas orchestral
    if 1400 < centroid < 3600 and 0.28 < onset < 0.72 and genre not in ('orchestral',):
        if not instruments or (len(instruments) == 1 and instruments[0] == 'percussions'):
            instruments.append('guitare')

    # Fallback par genre
    if not instruments:
        fallback = {
            'orchestral':    'cordes',
            'électronique':  'synthétiseur',
            'acoustique':    'guitare',
            'jazz':          'piano',
            'ambient':       'synthétiseur',
        }
        instruments.append(fallback.get(genre, 'synthétiseur'))

    return instruments[:2]


def detect_usage(genre, energy_tag, tempo, bpm):
    """Déduit 0 ou 1 usage probable."""
    high_energy = energy_tag in ('haute énergie', 'épique', 'action')
    low_energy  = energy_tag in ('faible énergie', 'calme')

    if genre == 'ambient' or low_energy:
        return 'documentaire'
    if genre == 'orchestral' and high_energy:
        return 'cinéma'
    if bpm > 118 and high_energy:
        return 'publicité'
    if genre == 'orchestral':
        return 'cinéma'
    return None


# ── Expansion sémantique des tags existants ───────────────────────────────────

SYNONYMES = {
    # Atmosphère / Émotion
    'tendu':         ['suspense', 'angoisse', 'thriller', 'anxieux', 'inquiétant', 'oppressant', 'stress'],
    'sombre':        ['ténébreux', 'obscur', 'noir', 'pesant', 'menaçant', 'dark'],
    'dramatique':    ['cinématique', 'théâtral', 'bouleversant', 'poignant', 'tragique'],
    'mélancolique':  ['nostalgique', 'triste', 'élégiaque', 'plaintif', 'lacrimeux'],
    'épique':        ['héroïque', 'grandiose', 'triomphal', 'aventure', 'conquête'],
    'intense':       ['percutant', 'fort', 'vigoureux', 'impactant'],
    'puissant':      ['robuste', 'massif', 'imposant', 'écrasant'],
    'énergique':     ['dynamique', 'tonique', 'vif', 'nerveux'],
    'festif':        ['célébration', 'fête', 'allègre', 'jubilant', 'exubérant'],
    'joyeux':        ['gai', 'enjoué', 'pétillant', 'léger', 'radieux'],
    'lumineux':      ['clair', 'ensoleillé', 'optimiste', 'radieux', 'brillant'],
    'positif':       ['optimiste', 'encourageant', 'inspirant', 'motivant'],
    'calme':         ['paisible', 'serein', 'tranquille', 'apaisant', 'zen'],
    'introspectif':  ['méditatif', 'recueilli', 'intérieur', 'contemplatif'],
    'contemplatif':  ['méditatif', 'recueilli', 'introspectif', 'pensif'],
    'doux':          ['tendre', 'délicat', 'velouté', 'suave'],
    # Énergie
    'haute énergie': ['action', 'boost', 'puissant', 'percutant'],
    'faible énergie':['ambient', 'discret', 'fond sonore'],
    # Tempo
    'rapide':        ['nerveux', 'pressé', 'entraînant'],
    'très rapide':   ['frénétique', 'effréné', 'haletant'],
    'lent':          ['posé', 'grave', 'solennel'],
    'très lent':     ['solennel', 'majestueux', 'hypnotique'],
    # Usage contextuel
    'cinéma':        ['film', 'bande originale', 'BO', 'soundtrack', 'score'],
    'publicité':     ['spot', 'commercial', 'jingle', 'marque'],
    'documentaire':  ['reportage', 'nature', 'exploration', 'témoignage'],
}

def expand_synonyms(existing_tags):
    """Retourne les synonymes des tags existants pas encore présents."""
    existing_lower = {t.lower() for t in existing_tags}
    additions = []
    for tag in existing_tags:
        for syn in SYNONYMES.get(tag.lower(), []):
            if syn not in existing_lower and syn not in additions:
                additions.append(syn)
    return additions


# ── Téléchargement ────────────────────────────────────────────────────────────

def download(url):
    fname = CACHE_DIR / (hashlib.md5(url.encode()).hexdigest() + '.mp3')
    if fname.exists():
        return fname
    r = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
    r.raise_for_status()
    fname.write_bytes(r.content)
    return fname


# ── Analyse principale ────────────────────────────────────────────────────────

def analyze_v2(url, existing_tags):
    path = download(url)
    y, sr = librosa.load(str(path), duration=ANALYZE_SEC, sr=22050, mono=True)
    if len(y) < sr * 2:
        return None

    existing_lower = {t.lower() for t in existing_tags}

    # Features communes
    zcr      = _f(np.mean(librosa.feature.zero_crossing_rate(y)))
    centroid = _f(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    contrast = _f(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))
    onset    = _f(np.mean(librosa.onset.onset_strength(y=y, sr=sr)))
    bpm      = _f(librosa.beat.beat_track(y=y, sr=sr)[0])

    # Énergie déjà présente dans les tags existants
    energy_tag = next(
        (t for t in existing_tags if 'énergie' in t or t in ('calme', 'épique', 'action')),
        'énergie moyenne'
    )

    new_tags = []

    # 1. BPM comme tag searchable (si pas déjà présent)
    # Librosa double/divise parfois le tempo — on le ramène dans 60-180
    while bpm > 180: bpm /= 2
    while bpm < 60:  bpm *= 2
    bpm_rounded = round(bpm / 5) * 5  # arrondi à 5 près : 118 → 120
    bpm_tag = f"{bpm_rounded} bpm"
    if not any('bpm' in t.lower() for t in existing_tags):
        new_tags.append(bpm_tag)

    # 2. Genre
    genre_tags = ('orchestral', 'électronique', 'acoustique', 'jazz', 'ambient', 'hybride')
    if not any(t in genre_tags for t in existing_tags):
        genre = detect_genre(y, sr, bpm, zcr, centroid, contrast, onset)
        new_tags.append(genre)
    else:
        genre = next((t for t in existing_tags if t in genre_tags), 'hybride')

    # 4. Instruments
    instr_tags = ('piano', 'cordes', 'cuivres', 'guitare', 'percussions', 'basse', 'synthétiseur')
    if not any(t in instr_tags for t in existing_tags):
        new_tags.extend(detect_instruments(y, sr, centroid, zcr, onset, genre))

    # 5. Usage
    usage_tags = ('cinéma', 'publicité', 'documentaire')
    if not any(t in usage_tags for t in existing_tags):
        usage = detect_usage(genre, energy_tag, bpm, bpm)
        if usage:
            new_tags.append(usage)

    # 6. Expansion sémantique des tags existants
    new_tags.extend(expand_synonyms(existing_tags))

    # Dédoublonnage final
    new_tags = [t for t in new_tags if t.lower() not in existing_lower]
    return new_tags


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with open(CATALOGUE, encoding='utf-8') as f:
        data = json.load(f)
    tracks = data['tracks']

    done = set(json.loads(PROGRESS.read_text())) if PROGRESS.exists() else set()
    todo = [
        t for t in tracks
        if t['id'] not in done
        and not any(tag in V2_MARKERS for tag in t.get('tags', []))
    ]

    print(f"\n🎵 OSM — Analyse v2  ·  Tonalité · Vocal · Genre · Instruments · Usage")
    print(f"   {len(tracks)} morceaux  ·  {len(done)} déjà faits  ·  {len(todo)} à analyser")
    est_min = len(todo) * 2 // 60
    print(f"   Durée estimée : ~{est_min // 60}h{est_min % 60:02d}min  (reprend si interrompu)\n")

    errors   = []
    saved_at = len(done)

    for track in todo:
        existing = track.get('tags', [])
        pct  = (len(done) + 1) / len(tracks) * 100
        print(f"[{len(done)+1}/{len(tracks)}  {pct:.1f}%]  {track['title'][:44]:<44}", end=' ', flush=True)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(analyze_v2, track['url'], existing)
                new_tags = future.result(timeout=90)
            if new_tags is None:
                print("⚠  trop court, ignoré")
            else:
                track['tags'] = existing + new_tags
                summary = ' · '.join(new_tags) if new_tags else '(déjà complet)'
                print(f"✓  {summary}")
        except concurrent.futures.TimeoutError:
            print("⏱  timeout, ignoré")
            errors.append({'title': track['title'], 'error': 'timeout 90s'})
        except Exception as e:
            msg = str(e)[:65]
            print(f"✗  {msg}")
            errors.append({'title': track['title'], 'error': msg})

        done.add(track['id'])
        PROGRESS.write_text(json.dumps(list(done)))

        if len(done) - saved_at >= SAVE_EVERY:
            data['tracks'] = tracks
            with open(CATALOGUE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            saved_at = len(done)
            print(f"\n   💾  Sauvegarde catalogue.json — {len(done)}/{len(tracks)} faits\n")

    # Sauvegarde finale
    data['tracks'] = tracks
    with open(CATALOGUE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    PROGRESS.unlink(missing_ok=True)

    print(f"\n✅  Terminé !  {len(done)} analysés,  {len(errors)} erreurs.")
    if errors:
        print("Erreurs :")
        for e in errors[:10]:
            print(f"  • {e['title']}: {e['error']}")

    if not errors:
        import shutil
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        print("🗑  Cache audio supprimé.")

    input("\nAppuie sur Entrée pour fermer...")
