#!/usr/bin/env python3
"""
Moteur de matching tracks ↔ critères prospect.

Scoring (par track candidate) :
  +1 par ambiance matchée
  +1 par niveau d'énergie matché
  +1 par tempo matché
  +1 si mode majeur/mineur matché

Sélection finale (top_n tracks) :
  1. Trier par score décroissant
  2. Parmi ex-æquo : pénalité -1 si BPM exact déjà présent dans la sélection
  3. Départage résiduel : BPM le plus proche de la médiane des candidats
"""

import json
import statistics
from pathlib import Path

BASE = Path(__file__).parent.parent

# Normalisation énergie : label prospect → tag catalogue
ENERGIE_MAP = {
    "basse":   "faible énergie",
    "faible":  "faible énergie",
    "moyenne": "énergie moyenne",
    "haute":   "haute énergie",
}

# Tags non-ambiance à exclure de l'affichage mood
_EXCLU_MOOD = {
    "majeur", "mineur", "graves", "équilibré", "aigus",
    "haute énergie", "énergie moyenne", "basse énergie", "faible énergie",
    "lent", "modéré", "rapide", "très rapide", "très lent",
}
_NOTES = {"do", "ré", "mi", "fa", "sol", "la", "si"}


def clean_title(title: str) -> str:
    """Supprime les espaces multiples et strip."""
    import re
    return re.sub(r' {2,}', ' ', title).strip()


def mood_tags(track: dict) -> list[str]:
    """Retourne les tags d'ambiance d'une track (sans mode, tempo, énergie, tonalité)."""
    result = []
    for tag in track.get("tags", []):
        tl = tag.lower()
        if tl in _EXCLU_MOOD:
            continue
        if any(tl == n or tl.startswith(n + ' ') or tl.startswith(n + '#') or tl.startswith(n + 'b')
               for n in _NOTES):
            continue
        result.append(tag)
    return result


def base_score(track: dict, criteres: dict) -> int:
    """Score brut : nombre de critères matchés."""
    tags = {t.lower() for t in track.get("tags", [])}
    score = 0

    for amb in criteres.get("ambiances", []):
        if amb.lower() in tags:
            score += 1

    for niv in criteres.get("energie", []):
        tag_cible = ENERGIE_MAP.get(niv.lower(), niv.lower())
        if tag_cible in tags:
            score += 1

    for tempo in criteres.get("tempo", []):
        if tempo.lower() in tags:
            score += 1

    mode = criteres.get("tonalite_mode", "")
    if mode and mode.lower() in tags:
        score += 1

    return score


def match_tracks(catalogue_path: str, criteres: dict, top_n: int = 5) -> list[dict]:
    """
    Retourne les top_n meilleures tracks avec scoring + diversité BPM.
    """
    with open(catalogue_path, encoding="utf-8") as f:
        data = json.load(f)
    tracks = data["tracks"]

    # 1. Scorer toutes les tracks candidates (score > 0)
    candidates = []
    for t in tracks:
        if not t.get("bpm"):
            continue
        s = base_score(t, criteres)
        if s > 0:
            candidates.append((s, t))

    if not candidates:
        return []

    # Médiane BPM des candidates (pour le départage)
    median_bpm = statistics.median(c[1]["bpm"] for c in candidates)

    # 2. Trier par score décroissant, puis BPM proche de la médiane
    candidates.sort(key=lambda x: (-x[0], abs(x[1]["bpm"] - median_bpm)))

    # 3. Sélection avec bonus diversité BPM
    selected: list[dict] = []
    selected_bpms: list[int] = []

    for score, track in candidates:
        bpm = track["bpm"]
        # Pénalité si BPM exact déjà présent dans la sélection
        effective_score = score - selected_bpms.count(bpm)
        # On insère en respectant l'ordre effectif
        inserted = False
        for i, existing in enumerate(selected):
            ex_score = base_score(existing, criteres) - selected_bpms[:i].count(existing["bpm"])
            if effective_score > ex_score:
                selected.insert(i, track)
                selected_bpms.insert(i, bpm)
                inserted = True
                break
        if not inserted:
            selected.append(track)
            selected_bpms.append(bpm)
        if len(selected) >= top_n:
            break

    return selected[:top_n]


if __name__ == "__main__":
    catalogue = BASE / "catalogue.json"
    criteres_demo = {
        "ambiances":     ["sombre", "mélancolique"],
        "energie":       ["basse", "moyenne"],
        "tempo":         ["lent", "modéré"],
        "tonalite_mode": "mineur",
    }
    results = match_tracks(str(catalogue), criteres_demo, top_n=5)
    print(f"Top {len(results)} tracks :\n")
    for t in results:
        s = base_score(t, criteres_demo)
        moods = ", ".join(mood_tags(t)[:3])
        print(f"  [{s} pts | {t['bpm']} bpm] {clean_title(t['title'])}  ({t['playlist']})")
        print(f"    Tags ambiance : {moods}")
        print()
