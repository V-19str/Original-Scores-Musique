#!/usr/bin/env python3
"""
Orchestrateur : génère un pitch .md par prospect "a_contacter".
"""

import json
import sys
from datetime import datetime
from pathlib import Path

BASE      = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent

sys.path.insert(0, str(AGENT_DIR))
from match_tracks import match_tracks, base_score as score_track, clean_title, mood_tags


# ── Helpers ───────────────────────────────────────────────────────────────────

ACCROCHES = {
    "documentaire": "un beau sujet qui mérite une musique à sa hauteur",
    "fiction":      "un projet où chaque scène respire",
    "publicité":    "une image qui gagne en force avec la bonne signature sonore",
    "animation":    "un univers où la musique construit les émotions",
    "corporate":    "un film qui doit toucher autant qu'il informe",
}

def accroche_pour(segment: str) -> str:
    return ACCROCHES.get(segment.lower(), "un projet qui mérite une musique à sa hauteur")


def format_tracks_md(tracks: list[dict]) -> str:
    lines = []
    for i, t in enumerate(tracks, 1):
        moods = mood_tags(t)
        mood  = ", ".join(moods[:3]) if moods else t.get("playlist", "")
        lines.append(
            f"{i}. **{clean_title(t['title'])}** — {t['bpm']} bpm, {t.get('playlist','')} "
            f"| _{mood}_  \n"
            f"   🎧 {t['url']}"
        )
    return "\n\n".join(lines)


def get_top3(catalogue_path: str, criteres: dict) -> list[dict]:
    top10 = match_tracks(catalogue_path, criteres, top_n=10)
    seen_titles, top3 = set(), []
    for t in top10:
        key = t["title"].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            top3.append(t)
        if len(top3) == 3:
            break
    return top3


def generate_pitch(prospect: dict, template: str, catalogue_path: str, nb_tracks: int) -> str:
    criteres = prospect["criteres_matching"]

    top3 = get_top3(catalogue_path, criteres)

    if not top3:
        return f"# Aucune track trouvée pour {prospect['boite']}\n"

    nom = prospect.get("contact_nom") or ""
    contact_prenom = nom.split()[0] if nom.strip() else "l'équipe"
    accroche       = accroche_pour(prospect.get("segment", ""))
    tracks_html    = format_tracks_md(top3)

    pitch = (template
             .replace("{{contact_prenom}}", contact_prenom)
             .replace("{{projet_recent}}", prospect.get("projet_recent", "votre dernier projet"))
             .replace("{{accroche}}", accroche)
             .replace("{{nb_tracks}}", str(nb_tracks))
             .replace("{{tracks_html}}", tracks_html))

    # Header métadonnées
    scores = [score_track(t, criteres) for t in top3]
    header = (
        f"<!-- Prospect : {prospect['boite']} ({prospect['id']}) -->\n"
        f"<!-- Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"
        f"<!-- Scores : {scores} | Critères : {criteres} -->\n\n"
    )
    return header + pitch


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    catalogue_path = str(BASE / "catalogue.json")
    prospects_path = AGENT_DIR / "prospects.json"
    template_path  = AGENT_DIR / "pitch_template.md"
    output_dir     = AGENT_DIR / "pitchs_generes"
    output_dir.mkdir(exist_ok=True)

    with open(catalogue_path, encoding="utf-8") as f:
        nb_tracks = len(json.load(f)["tracks"])

    with open(prospects_path, encoding="utf-8") as f:
        prospects = json.load(f)

    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    cibles = [p for p in prospects if p.get("statut") == "a_contacter"]
    print(f"\n🎵 OSM Agent commercial — {len(cibles)} prospect(s) à traiter\n")

    recap = []
    for p in cibles:
        pitch = generate_pitch(p, template, catalogue_path, nb_tracks)
        out_file = output_dir / f"{p['id']}.md"
        out_file.write_text(pitch, encoding="utf-8")

        track_names = [clean_title(t["title"]) for t in get_top3(catalogue_path, p["criteres_matching"])]

        print(f"  ✓  {p['boite']} ({p['id']})")
        print(f"     Tracks : {' · '.join(track_names)}")
        print(f"     → {out_file.relative_to(BASE)}\n")
        recap.append({"prospect": p["boite"], "fichier": str(out_file), "tracks": track_names})

    print(f"✅  {len(recap)} pitch(s) générés dans agent_osm/pitchs_generes/\n")
    return recap


if __name__ == "__main__":
    main()
