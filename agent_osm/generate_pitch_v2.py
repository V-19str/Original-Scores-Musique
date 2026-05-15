#!/usr/bin/env python3
"""
Brique 7 — Génération de pitchs v2 (données web vérifiées).

Utilise scans/{id}.json au lieu des criteres_matching manuels.
L'instruction à Claude mentionne les VRAIS projets trouvés sur le web.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE      = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent
SCANS_DIR = AGENT_DIR / "scans"

sys.path.insert(0, str(AGENT_DIR))
from match_tracks import match_tracks, base_score, clean_title, mood_tags, CATALOGUE_UNIQUE

MODEL        = "claude-opus-4-7"
CANDIDATES_N = 30

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

def format_candidate(t: dict, criteres: dict) -> str:
    score = base_score(t, criteres)
    moods = ", ".join(mood_tags(t)[:4]) or t.get("playlist", "")
    return (
        f'  id="{t["id"]}"  titre="{clean_title(t["title"])}"  '
        f'bpm={t["bpm"]}  playlist="{t.get("playlist","")}"  '
        f'score={score}  ambiances="{moods}"'
    )


def build_prompt_v2(prospect: dict, scan: dict, candidates: list[dict]) -> str:
    nom      = prospect["boite"]
    segment  = prospect.get("segment", "")
    criteres = scan.get("criteres_musicaux", {})

    projets = scan.get("projets_recents", [])
    projets_txt = "\n".join(
        f"  - {p.get('titre','')} ({p.get('type','')} {p.get('annee','')}) : {p.get('sujet','')}"
        for p in projets[:3]
    )

    contact_info = scan.get("contact", {})
    contact_nom  = contact_info.get("nom", "") or "l'équipe"
    cands_txt    = "\n".join(format_candidate(t, criteres) for t in candidates)

    return f"""Tu es conseiller musical pour OSM (Original Scores Music), catalogue de musiques originales pour le cinéma et l'audiovisuel.

## Prospect : {nom}
Segment : {segment}
Contact : {contact_nom}

## Projets RÉELS trouvés sur le web
{projets_txt}

## Ligne éditoriale
{scan.get("ligne_editoriale", "")}

## Angle pitch OSM recommandé
{scan.get("angle_pitch", "")}

## Catalogue OSM — {len(candidates)} candidats pré-filtrés

{cands_txt}

## Ta mission

1. Sélectionne les **3 meilleures tracks** pour ce prospect.
   - Appuie-toi sur les projets RÉELS listés ci-dessus pour justifier chaque choix.
   - Diversifie les playlists et BPM.
   - 1 phrase de justification éditoriale par track.

2. Rédige un **email de pitch en français**, chaleureux et pro, **60 à 100 mots**.
   - Mentionne **un projet réel** de la liste ci-dessus (titre exact).
   - Cite les 3 tracks choisies (titre + BPM).
   - Termine par une invitation à échanger.
   - Signature : "Vladimir — OSM / osm-music.fr"

## Format de réponse

JSON valide uniquement (sans balise markdown) :
{{
  "tracks_choisies": [{{"id": "...", "raison": "..."}}],
  "pitch_email": "..."
}}"""


def resolve_tracks(chosen: list[dict], candidates: list[dict]) -> list[dict]:
    by_id = {t["id"]: t for t in candidates}
    return [
        {**by_id[c["id"]], "raison": c["raison"]}
        for c in chosen
        if c["id"] in by_id
    ]


def format_md(prospect: dict, scan: dict, ai_tracks: list[dict],
              pitch_email: str, prompt: str, criteres: dict) -> str:
    projets = scan.get("projets_recents", [])
    projets_txt = "\n".join(
        f"- **{p.get('titre','')}** ({p.get('type','')} {p.get('annee','')}) : {p.get('sujet','')}"
        for p in projets
    )

    def track_line(t: dict) -> str:
        moods = ", ".join(mood_tags(t)[:3]) or t.get("playlist", "")
        return (
            f"- **{clean_title(t['title'])}** — {t['bpm']} bpm, {t.get('playlist','')} | _{moods}_  \n"
            f"  🎧 {t['url']}\n"
            f"  > {t.get('raison','')}"
        )

    ai_section  = "\n\n".join(track_line(t) for t in ai_tracks)
    scores      = [base_score(t, criteres) for t in ai_tracks]
    sources_txt = "\n".join(f"- {s}" for s in scan.get("sources", []))

    return (
        f"<!-- Prospect : {prospect['boite']} ({prospect['id']}) -->\n"
        f"<!-- Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"
        f"<!-- Modèle : {MODEL} (v2 — données web vérifiées) -->\n"
        f"<!-- Critères déduits du scan : {criteres} -->\n\n"
        f"# Pitch v2 — {prospect['boite']}\n\n"
        f"## Projets réels (sources web)\n\n{projets_txt}\n\n"
        f"*Ligne éditoriale : {scan.get('ligne_editoriale','')}*\n\n"
        f"---\n\n"
        f"## Email\n\n{pitch_email}\n\n"
        f"---\n\n"
        f"## Tracks choisies (scores : {scores})\n\n{ai_section}\n\n"
        f"---\n\n"
        f"## Sources web consultées\n\n{sources_txt}\n\n"
        f"<details><summary>Prompt envoyé à Claude</summary>\n\n"
        f"```\n{prompt}\n```\n\n"
        f"</details>\n"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def process_prospect(prospect: dict, output_dir: Path) -> dict:
    import anthropic
    client = anthropic.Anthropic()

    scan_path = SCANS_DIR / f"{prospect['id']}.json"
    if not scan_path.exists():
        print(f"  ⚠  Pas de scan pour {prospect['boite']} — ignoré")
        return {}

    with open(scan_path, encoding="utf-8") as f:
        scan = json.load(f)

    criteres   = scan.get("criteres_musicaux", {})
    candidates = match_tracks(str(CATALOGUE_UNIQUE), criteres, top_n=CANDIDATES_N)

    if not candidates:
        print(f"  ⚠  Aucune track candidate pour {prospect['boite']}")
        return {}

    prompt = build_prompt_v2(prospect, scan, candidates)

    print(f"  → Pitch v2 pour {prospect['boite']} ({len(candidates)} candidats)…")

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

    raw  = next(b.text for b in msg.content if getattr(b, "type", None) == "text")
    data = json.loads(raw)

    ai_tracks   = resolve_tracks(data["tracks_choisies"], candidates)
    pitch_email = data["pitch_email"]

    output_dir.mkdir(exist_ok=True)
    md = format_md(prospect, scan, ai_tracks, pitch_email, prompt, criteres)
    out_file = output_dir / f"{prospect['id']}.md"
    out_file.write_text(md, encoding="utf-8")

    names = [clean_title(t["title"]) for t in ai_tracks]
    print(f"  ✓  {prospect['boite']} → {' · '.join(names)}")
    print(f"     → {out_file.relative_to(BASE)}\n")
    return {"prospect": prospect["boite"], "tracks": names, "fichier": str(out_file)}


def main():
    prospects_path = AGENT_DIR / "prospects.json"
    output_dir     = AGENT_DIR / "pitchs_generes_v2"

    with open(prospects_path, encoding="utf-8") as f:
        prospects = json.load(f)

    cibles = [p for p in prospects if p.get("statut") == "scanne"]
    print(f"\n🎵 OSM Pitch v2 — {len(cibles)} prospect(s) scannés disponibles\n")

    results = []
    for p in cibles:
        r = process_prospect(p, output_dir)
        if r:
            results.append(r)

    print(f"✅  {len(results)} pitch(s) v2 générés dans agent_osm/pitchs_generes_v2/\n")
    return results


if __name__ == "__main__":
    main()
