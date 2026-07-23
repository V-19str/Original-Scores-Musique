#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrait les blocs de donnees confidentiels d'admin-sacem.html.

Contexte : admin-sacem.html etait servi publiquement (GitHub Pages) avec, en
dur dans son JavaScript, les revenus SACEM reels, le previsionnel et les noms +
revenus des co-auteurs. Le garde admin-guard.js est purement cote client : il
ne rend rien secret. Ces donnees sont donc deplacees dans Supabase, table
`sacem_data`, lisible par le seul administrateur (RLS sur l'email du JWT).

Ce script est l'outil de migration / mise a jour :
  - il lit les blocs encore presents dans admin-sacem.html (source historique),
    OU, une fois la page videe, dans sacem_data_source.json (source de verite) ;
  - il produit sacem_data_source.json : la source privee, hors depot ;
  - il produit sacem_data_seed.sql : les INSERT a passer dans Supabase.

Aucun des deux fichiers produits n'entre dans le depot (voir .gitignore) : ils
contiennent exactement ce qu'on retire du site.

Usage :
    python build_sacem_data.py --from-html   # extraction initiale depuis le HTML
    python build_sacem_data.py                # regenere le seed depuis le JSON
"""

import argparse
import ast
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, "admin-sacem.html")
SOURCE_JSON = os.path.join(ROOT, "sacem_data_source.json")
SEED_SQL = os.path.join(ROOT, "sacem_data_seed.sql")

# Les blocs deplaces. Tout ce qui porte des montants, du previsionnel ou des
# noms/revenus de tiers. Les libelles de chaines (CH_LABEL, CH_LBL), les
# coefficients de modele (COEFS), les listes de statuts et le jeu PROJETS_DEMO
# restent dans la page : ils ne revelent ni revenu ni identite.
MOVED = [
    "CAT_RICH", "CAT_PARTS", "PROGRAMMES", "COMPS_REVENU", "REVENUS_ANNEE",
    "REVENUS_VERSEMENTS", "TOP_MORCEAUX", "CHAINE_REV", "TYPES_REV", "PIPELINE",
    "DORMANTS", "PROGS_DETAIL", "OEUVRES_DETAIL", "VALDIFF", "PREV",
    "OSM_COMPOSERS", "TOTAL_REEL", "FOND_COMPOSERS",
]


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_value(raw):
    """Parse un litteral JS (JSON double-quote, ou tableau Python-compatible
    a simple quote comme OSM_COMPOSERS)."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Tableau/objet a simple quote : ast.literal_eval l'accepte.
        return ast.literal_eval(raw)


def extract_from_html(html):
    data = {}
    for var in MOVED:
        # Chaque bloc est sur une seule ligne : `let VAR = <literal>;`
        m = re.search(r"^\s*(?:let|const|var)\s+" + re.escape(var) +
                      r"\s*=\s*(.+?);\s*$", html, re.M)
        if not m:
            sys.exit("Bloc introuvable dans admin-sacem.html : %s" % var)
        data[var] = parse_value(m.group(1))
    return data


def write_json(data):
    with io.open(SOURCE_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_seed(data):
    lines = [
        "-- sacem_data_seed.sql — genere par build_sacem_data.py. NE PAS COMMITER.",
        "-- A executer dans Supabase (SQL Editor) apres la migration sacem_data.",
        "-- Contient les revenus et donnees SACEM retires d'admin-sacem.html.",
        "",
    ]
    for key in MOVED:
        payload = json.dumps(data[key], ensure_ascii=False, separators=(",", ":"))
        payload_sql = "'" + payload.replace("'", "''") + "'"
        lines.append(
            "insert into public.sacem_data (key, payload) values "
            "('%s', %s::jsonb)\n"
            "  on conflict (key) do update set payload = excluded.payload, "
            "updated_at = now();" % (key, payload_sql)
        )
    with io.open(SEED_SQL, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-html", action="store_true",
                    help="extrait depuis admin-sacem.html (premiere fois)")
    args = ap.parse_args()

    if args.from_html:
        data = extract_from_html(read(HTML))
    else:
        if not os.path.exists(SOURCE_JSON):
            sys.exit("sacem_data_source.json absent : lancez d'abord --from-html")
        data = json.loads(read(SOURCE_JSON))
        missing = [k for k in MOVED if k not in data]
        if missing:
            sys.exit("Cles manquantes dans le JSON : %s" % ", ".join(missing))

    write_json(data)
    write_seed(data)
    total = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in data.values())
    print("%d blocs extraits (%d entrees cumulees)" % (len(data), total))
    print("  -> %s" % os.path.basename(SOURCE_JSON))
    print("  -> %s" % os.path.basename(SEED_SQL))


if __name__ == "__main__":
    main()
