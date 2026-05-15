#!/usr/bin/env python3
"""
Brique 6 — Pitchs intelligents via Claude API.

Pipeline :
  1. Pré-filtrage mécanique : top-30 candidates via match_tracks.py
  2. Claude claude-opus-4-7 choisit les 3 meilleures + rédige l'email en français (≤100 mots)
  3. Réponse JSON structurée : {"tracks_choisies": [{"id","raison"}], "pitch_email": "..."}
  4. Sauvegarde dans pitchs_generes_ai/{id}.md avec comparaison sélection mécanique vs IA

Mode dry-run : si ANTHROPIC_API_KEY absente ou placeholder → affiche le prompt sans appel API.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE      = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent

sys.path.insert(0, str(AGENT_DIR))
from match_tracks import match_tracks, base_score, clean_title, mood_tags, CATALOGUE_UNIQUE

CANDIDATES_N = 30
TOP_N        = 3
MODEL        = "claude-opus-4-7"

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tracks_choisies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id":     {"type": "string"},
                    "raison": {"type": "string"},
                },
                "required": ["id", "raison"],
            },
        },
        "pitch_email": {"type": "string"},
    },
    "required": ["tracks_choisies", "pitch_email"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_dry_run() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return not key or key.startswith("xxx") or key.startswith("sk-ant-xxx")


def format_candidate(t: dict, criteres: dict) -> str:
    score = base_score(t, criteres)
    moods = ", ".join(mood_tags(t)[:4]) or t.get("playlist", "")
    return (
        f'  id="{t["id"]}"  titre="{clean_title(t["title"])}"  '
        f'bpm={t["bpm"]}  playlist="{t.get("playlist","")}"  '
        f'score_mecanique={score}  ambiances="{moods}"'
    )


def build_prompt(prospect: dict, candidates: list[dict]) -> str:
    criteres    = prospect["criteres_matching"]
    boite       = prospect["boite"]
    segment     = prospect.get("segment", "")
    projet      = prospect.get("projet_recent", "")
    contact_nom = prospect.get("contact_nom", "") or "l'équipe"

    ambiances = ", ".join(criteres.get("ambiances", []))
    energie   = ", ".join(criteres.get("energie", []))
    tempo     = ", ".join(criteres.get("tempo", []))
    mode      = criteres.get("tonalite_mode", "")

    cands_txt = "\n".join(format_candidate(t, criteres) for t in candidates)

    return f"""Tu es conseiller musical pour OSM (Original Scores Music), un catalogue de musiques originales pour le cinéma et l'audiovisuel.

## Contexte prospect

- Société : {boite}
- Segment : {segment}
- Projet récent : {projet}
- Contact : {contact_nom}

## Critères musicaux recherchés

- Ambiances : {ambiances}
- Énergie : {energie}
- Tempo : {tempo}
- Tonalité : {mode}

## Catalogue pré-filtré ({len(candidates)} candidats)

{cands_txt}

## Ta mission

1. Parmi ces {len(candidates)} tracks, sélectionne les **3 meilleures** pour ce prospect.
   - Privilégie la diversité (BPM varié, ambiances complémentaires).
   - Pour chaque track choisie, explique en **une phrase** pourquoi elle convient à ce projet.

2. Rédige un **email de pitch en français**, chaleureux et professionnel, de **60 à 100 mots** (corps uniquement, sans "Objet:").
   - Mentionne le projet récent du prospect.
   - Cite les 3 tracks choisies (titre + BPM).
   - Termine par une invitation à échanger.
   - Signature : "Vladimir — OSM / osm-music.fr"

## Format de réponse

Réponds **uniquement** avec un objet JSON valide, sans balises markdown, selon ce schéma :
{{
  "tracks_choisies": [
    {{"id": "<id_track>", "raison": "<une phrase>"}},
    ...
  ],
  "pitch_email": "<texte de l'email>"
}}"""


def resolve_tracks(chosen: list[dict], candidates: list[dict]) -> list[dict]:
    """Retrouve les dicts complets des tracks choisies par Claude."""
    by_id = {t["id"]: t for t in candidates}
    result = []
    for c in chosen:
        track = by_id.get(c["id"])
        if track:
            result.append({**track, "raison": c["raison"]})
    return result


def format_md(prospect: dict, ai_tracks: list[dict], pitch_email: str,
              mech_tracks: list[dict], prompt: str, catalogue_path: str) -> str:
    criteres = prospect["criteres_matching"]

    def track_line(t: dict) -> str:
        moods = ", ".join(mood_tags(t)[:3]) or t.get("playlist", "")
        return (
            f"- **{clean_title(t['title'])}** — {t['bpm']} bpm, {t.get('playlist','')} | _{moods}_  \n"
            f"  🎧 {t['url']}"
        )

    ai_section = "\n\n".join(
        track_line(t) + f"\n  > {t.get('raison','')}" for t in ai_tracks
    )
    mech_section = "\n\n".join(track_line(t) for t in mech_tracks)

    scores_ai   = [base_score(t, criteres) for t in ai_tracks]
    scores_mech = [base_score(t, criteres) for t in mech_tracks]

    return (
        f"<!-- Prospect : {prospect['boite']} ({prospect['id']}) -->\n"
        f"<!-- Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"
        f"<!-- Modèle : {MODEL} -->\n"
        f"<!-- Critères : {criteres} -->\n\n"
        f"# Pitch IA — {prospect['boite']}\n\n"
        f"## Email\n\n"
        f"{pitch_email}\n\n"
        f"---\n\n"
        f"## Tracks choisies par Claude (scores : {scores_ai})\n\n"
        f"{ai_section}\n\n"
        f"---\n\n"
        f"## Sélection mécanique (scores : {scores_mech})\n\n"
        f"{mech_section}\n\n"
        f"---\n\n"
        f"<details><summary>Prompt envoyé à Claude</summary>\n\n"
        f"```\n{prompt}\n```\n\n"
        f"</details>\n"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def process_prospect(prospect: dict, catalogue_path: str, output_dir: Path) -> dict:
    criteres = prospect["criteres_matching"]

    # 1. Pré-filtrage mécanique
    candidates  = match_tracks(catalogue_path, criteres, top_n=CANDIDATES_N)
    mech_top3   = candidates[:TOP_N]

    if not candidates:
        print(f"  ⚠  Aucune track candidate pour {prospect['boite']}")
        return {}

    prompt = build_prompt(prospect, candidates)

    if is_dry_run():
        print("\n" + "═" * 70)
        print(f"  DRY-RUN — prospect : {prospect['boite']} ({prospect['id']})")
        print(f"  Candidats pré-filtrés : {len(candidates)}")
        print("═" * 70 + "\n")
        print("── PROMPT COMPLET ──────────────────────────────────────────────────\n")
        print(prompt)
        print("\n────────────────────────────────────────────────────────────────────")
        print("  (Aucun appel API — clé ANTHROPIC_API_KEY absente ou placeholder)")
        return {"dry_run": True, "prospect": prospect["boite"]}

    # 2. Appel Claude
    import anthropic
    client = anthropic.Anthropic()

    print(f"  → Appel {MODEL} pour {prospect['boite']} ({len(candidates)} candidats)…")

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        thinking={"type": "adaptive"},
        output_config={
            "format": {
                "type": "json_schema",
                "schema": JSON_SCHEMA,
            }
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()

    # 3. Parse JSON
    raw = next(
        b.text for b in msg.content if getattr(b, "type", None) == "text"
    )
    data = json.loads(raw)

    ai_tracks = resolve_tracks(data["tracks_choisies"], candidates)
    pitch_email = data["pitch_email"]

    # 4. Sauvegarde
    output_dir.mkdir(exist_ok=True)
    md = format_md(prospect, ai_tracks, pitch_email, mech_top3, prompt, str(CATALOGUE_UNIQUE))
    out_file = output_dir / f"{prospect['id']}.md"
    out_file.write_text(md, encoding="utf-8")

    ai_names   = [clean_title(t["title"]) for t in ai_tracks]
    mech_names = [clean_title(t["title"]) for t in mech_top3]

    print(f"  ✓  {prospect['boite']} ({prospect['id']})")
    print(f"     IA    : {' · '.join(ai_names)}")
    print(f"     Mécanique : {' · '.join(mech_names)}")
    print(f"     → {out_file.relative_to(BASE)}\n")

    return {
        "prospect":  prospect["boite"],
        "fichier":   str(out_file),
        "ai_tracks": ai_names,
        "mech_tracks": mech_names,
    }


def main():
    catalogue_path = str(CATALOGUE_UNIQUE)
    prospects_path = AGENT_DIR / "prospects.json"
    output_dir     = AGENT_DIR / "pitchs_generes_ai"

    with open(prospects_path, encoding="utf-8") as f:
        prospects = json.load(f)

    cibles = [p for p in prospects if p.get("statut") == "a_contacter"]

    mode_label = "DRY-RUN" if is_dry_run() else f"via {MODEL}"
    print(f"\n🎵 OSM Agent IA [{mode_label}] — {len(cibles)} prospect(s)\n")

    results = []
    for p in cibles:
        r = process_prospect(p, catalogue_path, output_dir)
        if r:
            results.append(r)

    if not is_dry_run():
        print(f"✅  {len(results)} pitch(s) IA générés dans agent_osm/pitchs_generes_ai/\n")

    return results


if __name__ == "__main__":
    main()
