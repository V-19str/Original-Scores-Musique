#!/usr/bin/env python3
"""
Brique 7 — Scanner web autonome.

Pour chaque prospect "a_scanner" :
  1. Claude claude-opus-4-7 fait des recherches web (web_search server-side
     + web_fetch client-side)
  2. Produit un JSON structuré → scans/{id}.json
  3. Met à jour le statut dans prospects.json

Sécurités :
  - web_fetch timeout → continue avec web_search seul
  - Aucun projet trouvé → statut "scan_vide", pas de pitch
  - Log complet dans scans_log.md
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic

BASE      = Path(__file__).parent.parent
AGENT_DIR = Path(__file__).parent
SCANS_DIR = AGENT_DIR / "scans"
MODEL     = "claude-opus-4-7"

WEB_FETCH_TOOL = {
    "name": "web_fetch",
    "description": (
        "Récupère le contenu texte d'une page web. "
        "Utilise pour lire le site officiel d'une société de production."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "url": {"type": "string", "description": "URL complète à charger"}
        },
        "required": ["url"],
    },
}


# ── Utilitaires ───────────────────────────────────────────────────────────────

def fetch_url(url: str, max_chars: int = 6000) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "html" not in ct and "text" not in ct:
                return f"[Non-texte: {ct}]"
            html = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        for ent, rep in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                         ("&gt;", ">"), ("&#39;", "'"), ("&quot;", '"')]:
            text = text.replace(ent, rep)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"[Erreur fetch: {e}]"


def extract_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            result = json.loads(m.group())
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return None


def block_to_dict(block) -> dict:
    """Sérialise un bloc SDK Anthropic en dict JSON-compatible."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if hasattr(block, "__dict__"):
        return {k: v for k, v in block.__dict__.items() if not k.startswith("_")}
    return block  # already a dict


# ── Scanner principal ─────────────────────────────────────────────────────────

def scan_prospect(prospect: dict, client: anthropic.Anthropic, log: list) -> dict | None:
    nom     = prospect["boite"]
    site    = prospect.get("site_web", "")
    segment = prospect.get("segment", "")
    pid     = prospect["id"]

    log.append(f"\n### {nom} ({pid})")
    log.append(f"- Site : {site}  |  Segment : {segment}")
    log.append(f"- Début : {datetime.now().strftime('%H:%M:%S')}")

    system = f"""Tu es un assistant de prospection pour OSM (Original Scores Music), catalogue de musiques originales pour le cinéma, la TV et le corporate.

Ta mission : trouver les projets récents de **{nom}** ({site}) pour personnaliser un pitch musical.

Vocabulaire OSM strict (utilise uniquement ces valeurs) :
- ambiances : sombre, lumineux, mélancolique, festif, énergique, joyeux, positif, puissant, épique, intense, dramatique, tendu, calme, contemplatif
- energie : basse, moyenne, haute
- tempo : lent, modéré, rapide"""

    user_msg = f"""Recherche les informations récentes sur **{nom}** en faisant ces étapes dans l'ordre :

1. web_search : "{nom} production 2024 2025"
2. web_search : "{nom} {segment} film récent"
3. web_fetch : https://{site}

Si le site officiel a une page /productions, /films, /projets ou /actualites, fais aussi un web_fetch dessus.

Réponds UNIQUEMENT avec un objet JSON valide (sans balise markdown) :
{{
  "projets_recents": [
    {{"titre": "...", "type": "documentaire|fiction|corporate|série|court-métrage", "annee": "2024|2025|...", "sujet": "description courte"}}
  ],
  "ligne_editoriale": "identité éditoriale en 1 phrase",
  "angle_pitch": "comment pitcher OSM à cette boîte (1-2 phrases)",
  "criteres_musicaux": {{
    "ambiances": ["tag1", "tag2"],
    "energie": ["basse|moyenne|haute"],
    "tempo": ["lent|modéré|rapide"]
  }},
  "contact": {{"nom": "", "role": "", "email": ""}},
  "sources": ["url1", "url2"]
}}"""

    messages = [{"role": "user", "content": user_msg}]
    tools = [
        {"type": "web_search_20250305", "name": "web_search"},
        {"type": "web_fetch_20260309",  "name": "web_fetch"},
    ]

    for i in range(14):
        try:
            resp = client.beta.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=messages,
                betas=["web-search-2025-03-05"],
            )
        except Exception as e:
            log.append(f"  ✗ Erreur API iter {i+1}: {e}")
            return None

        block_types = [getattr(b, "type", "?") for b in resp.content]
        log.append(f"  iter {i+1}: stop={resp.stop_reason}  blocks={block_types}")

        # Ajoute la réponse assistant (inclut tool_use + tool_result web_search server-side)
        messages.append({
            "role": "assistant",
            "content": [block_to_dict(b) for b in resp.content],
        })

        # Fin : extraire le JSON (concaténer tous les blocs text)
        if resp.stop_reason == "end_turn":
            all_text = " ".join(
                getattr(b, "text", "")
                for b in resp.content
                if getattr(b, "text", None)
            )
            data = extract_json(all_text)
            if data:
                log.append(f"  ✓ JSON extrait ({len(str(data))} chars)")
                return data
            log.append(f"  ✗ Pas de JSON valide (texte total : {len(all_text)} chars)")
            return None

        # Tous les tools sont server-side (web_search + web_fetch) :
        # l'API exécute et inclut les résultats dans le contenu.
        # On log juste les appels pour le debug.
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                log.append(f"  {block.name} → {list(block.input.values())[:1]}")

    log.append("  ✗ Max itérations atteintes sans résultat")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    SCANS_DIR.mkdir(exist_ok=True)
    prospects_path = AGENT_DIR / "prospects.json"
    log_path       = AGENT_DIR / "scans_log.md"

    with open(prospects_path, encoding="utf-8") as f:
        prospects = json.load(f)

    cibles = [p for p in prospects if p.get("statut") == "a_scanner"]
    print(f"\n🔍 OSM Scanner web — {len(cibles)} prospect(s) à scanner\n")

    log = [
        f"# Scans log OSM",
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"Modèle : {MODEL}",
        f"Prospects : {len(cibles)}\n",
        "---",
    ]

    for p in cibles:
        print(f"  → {p['boite']} ({p['id']}) …")
        data = scan_prospect(p, anthropic.Anthropic(), log)

        if data and data.get("projets_recents"):
            # Sauvegarde scan
            scan_file = SCANS_DIR / f"{p['id']}.json"
            scan_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # Met à jour statut
            p["statut"] = "scanne"
            projets = [pr.get("titre", "?") for pr in data["projets_recents"][:3]]
            print(f"  ✓  {p['boite']} — {len(data['projets_recents'])} projet(s) : {', '.join(projets)}")
            log.append(f"  → **Statut : scanne** — {len(data['projets_recents'])} projet(s)")
        else:
            p["statut"] = "scan_vide"
            print(f"  ⚠  {p['boite']} — scan vide, pas de pitch généré")
            log.append(f"  → **Statut : scan_vide**")

        print()

    # Sauvegarde prospects.json mis à jour
    with open(prospects_path, "w", encoding="utf-8") as f:
        json.dump(prospects, f, ensure_ascii=False, indent=2)

    # Écrit le log
    log_path.write_text("\n".join(log), encoding="utf-8")

    scanne   = [p for p in prospects if p.get("statut") == "scanne"]
    vide     = [p for p in prospects if p.get("statut") == "scan_vide"]
    print(f"✅  Scan terminé : {len(scanne)} scannés, {len(vide)} vides")
    print(f"   Log → agent_osm/scans_log.md\n")


if __name__ == "__main__":
    main()
