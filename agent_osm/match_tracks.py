#!/usr/bin/env python3
"""
Moteur de matching tracks ↔ critères prospect.
Score = nombre de critères matchés ; départage par BPM proche de la médiane.
"""

import json
import statistics
from pathlib import Path

BASE = Path(__file__).parent.parent

# Normalisation énergie : label prospect → tag catalogue
ENERGIE_MAP = {
    "basse":   "basse énergie",
    "moyenne": "énergie moyenne",
    "haute":   "haute énergie",
}


def score_track(track: dict, criteres: dict) -> int:
    tags = {t.lower() for t in track.get("tags", [])}
    score = 0

    # Ambiances — +1 par ambiance matchée
    for amb in criteres.get("ambiances", []):
        if amb.lower() in tags:
            score += 1

    # Énergie — +1 par niveau d'énergie matché
    for niv in criteres.get("energie", []):
        tag_cible = ENERGIE_MAP.get(niv.lower(), niv.lower())
        if tag_cible in tags:
            score += 1

    # Tempo — +1 par tempo matché
    for tempo in criteres.get("tempo", []):
        if tempo.lower() in tags:
            score += 1

    # Tonalité (mode majeur/mineur) — +1 si matché
    mode = criteres.get("tonalite_mode", "")
    if mode and mode.lower() in tags:
        score += 1

    return score


def match_tracks(catalogue_path: str, criteres: dict, top_n: int = 5) -> list[dict]:
    with open(catalogue_path, encoding="utf-8") as f:
        data = json.load(f)
    tracks = data["tracks"]

    scored = []
    for t in tracks:
        if not t.get("bpm"):
            continue
        s = score_track(t, criteres)
        if s > 0:
            scored.append((s, t))

    if not scored:
        return []

    # Médiane BPM des tracks candidates
    bpms = [t["bpm"] for _, t in scored]
    median_bpm = statistics.median(bpms)

    # Tri : score décroissant, puis BPM le plus proche de la médiane
    scored.sort(key=lambda x: (-x[0], abs(x[1]["bpm"] - median_bpm)))

    return [t for _, t in scored[:top_n]]


if __name__ == "__main__":
    catalogue = BASE / "catalogue.json"
    criteres_demo = {
        "ambiances": ["sombre", "mélancolique"],
        "energie":   ["basse", "moyenne"],
        "tempo":     ["lent", "modéré"],
        "tonalite_mode": "mineur",
    }
    results = match_tracks(str(catalogue), criteres_demo, top_n=5)
    print(f"Top {len(results)} tracks :\n")
    for t in results:
        score = score_track(t, criteres_demo)
        print(f"  [{score} pts | {t['bpm']} bpm] {t['title']}  ({t['playlist']})")
        print(f"    Tags: {', '.join(t['tags'])}")
        print()
