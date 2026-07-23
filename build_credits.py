#!/usr/bin/env python3
"""
build_credits.py
────────────────
Produit credits.json : titre du catalogue → compositeurs et clés de répartition,
donnée indispensable au générateur de cue sheet SACEM côté client.

La source est sacem_data_source.json (hors dépôt, produit par
build_sacem_data.py) : les blocs confidentiels d'admin-sacem.html — dont
CAT_PARTS et les revenus — y ont été déplacés lorsque la page a été vidée.
Ce script n'extrait que CAT_PARTS — nom du compositeur et pourcentage — et
refuse d'écrire si la sortie contient la moindre trace des blocs de revenus.

Appariement avec catalogue.json :
  1. titre normalisé (accents, casse et ponctuation neutralisés)
  2. à défaut, titre de base : « Bubble Mvcvm - Rithmic Version » → « Bubble Mvcvm »
Les titres non appariés sont laissés hors du fichier : le générateur affichera
un champ compositeur vide à compléter, plutôt qu'une donnée devinée.

Usage :
    python build_credits.py
    python build_credits.py --check    # verifie sans ecrire
"""

import argparse, json, re, sys, unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE = "sacem_data_source.json"
CATALOGUE = "catalogue.json"
OUTPUT = "credits.json"
SEED = "credits_seed.sql"

# Blocs confidentiels d'admin-sacem.html : aucun ne doit ressortir ici. On vise
# les identifiants exacts et des mots entiers — un motif large comme « CA_ »
# matcherait des identifiants legitimes du catalogue (AFRICA_MAN_JUV...).
FORBIDDEN = [r"REVENUS_ANNEE", r"REVENUS_VERSEMENTS", r"COMPS_REVENU",
             r"PROGRAMMES", r"CAT_RICH", r"\brevenus?\b", r"\bversements?\b",
             r"\bmontant\b", r"\bperiodes?\b", r"\bchaines?\b"]

SUFFIX_RE = re.compile(
    r"\b(FULL|LIGHT|RITHMIC|RYTHMIC|RHYTHMIC|NEW|FINAL|NO|SANS|VERSION"
    r"|V2|EDIT|MIX|JINGLE|COPIE DE)\b.*$"
)


def sql_quote(v):
    """Litteral SQL : on double les quotes, aucune interpolation brute."""
    return "'" + str(v).replace("'", "''") + "'"


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def base_title(n):
    return SUFFIX_RE.sub("", n).strip()


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_parts(raw):
    """CAT_PARTS : {"TITRE": [{"n": "Nom Prenom", "k": 25.0}, ...]},
    lu depuis sacem_data_source.json."""
    try:
        src = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit("%s illisible : lancez build_sacem_data.py" % SOURCE)
    if "CAT_PARTS" not in src:
        sys.exit("CAT_PARTS absent de %s" % SOURCE)
    return src["CAT_PARTS"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="n'ecrit pas le fichier")
    args = ap.parse_args()

    parts = extract_parts(read(SOURCE))
    tracks = json.loads(read(CATALOGUE))["tracks"]

    index = {}
    for title, people in parts.items():
        index.setdefault(norm(title), people)

    credits, direct, fallback = {}, 0, 0
    for t in tracks:
        n = norm(t["title"])
        people = index.get(n)
        if people:
            direct += 1
        else:
            b = base_title(n)
            people = index.get(b) if b else None
            if people:
                fallback += 1
        if not people:
            continue
        # On ne garde que le nom et la cle : rien d'autre ne sort d'admin-sacem.
        credits[t["id"]] = [
            {"nom": p["n"], "cle": round(float(p["k"]), 2)}
            for p in people if p.get("n")
        ]

    total = len(tracks)
    print("catalogue      : %d titres" % total)
    print("appariement    : %d direct + %d titre de base = %d (%.1f%%)"
          % (direct, fallback, direct + fallback,
             100.0 * (direct + fallback) / total))
    print("sans credits   : %d titres (champ a completer dans le cue sheet)"
          % (total - direct - fallback))

    payload = {
        "source": "admin-sacem.html (CAT_PARTS)",
        "note": "Compositeurs et cles de repartition uniquement. "
                "Aucune donnee de revenus.",
        "credits": credits,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=2)

    # Garde-fou : meme reservee aux monteurs connectes, cette donnee sort
    # d'un fichier qui contient les revenus — on verifie qu'on n'emporte que
    # les credits. Le controle porte sur les donnees extraites, pas sur
    # l'en-tete redige ci-dessus, qui mentionne « revenus » pour dire qu'il
    # n'y en a pas.
    extracted = json.dumps(credits, ensure_ascii=False)
    leaks = [p for p in FORBIDDEN if re.search(p, extracted, re.I)]
    if leaks:
        sys.exit("ARRET : la sortie contient %s — rien n'a ete ecrit." % leaks)

    sane = all(
        isinstance(v, list) and all(set(e) == {"nom", "cle"} for e in v)
        for v in credits.values()
    )
    if not sane:
        sys.exit("ARRET : structure inattendue — rien n'a ete ecrit.")

    if args.check:
        print("\n--check : %s non ecrit (%.0f Ko)" % (OUTPUT, len(blob) / 1024))
        return

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(blob)
    print("\nOK : %s, %d titres credites (%.0f Ko)"
          % (OUTPUT, len(credits), len(blob) / 1024))

    # Chargement de la table Supabase `credits` (RLS : lecture authentifiee).
    # Les deux fichiers sont gitignores : cette donnee ne doit pas devenir
    # publique, seul un monteur connecte doit pouvoir la lire.
    with open(SEED, "w", encoding="utf-8") as f:
        f.write("-- Genere par build_credits.py — NE PAS COMMITER.\n")
        f.write("-- Coller dans le SQL Editor Supabase apres la migration"
                " 20260721140000_credits.sql\n\n")
        # Upsert plutot que truncate + insert : un copier-coller interrompu
        # laisse la table incomplete au lieu de la vider.
        f.write("insert into public.credits (track_id, parts) values\n")
        rows = [
            "  (%s, %s::jsonb)" % (sql_quote(tid),
                                   sql_quote(json.dumps(p, ensure_ascii=False)))
            for tid, p in sorted(credits.items())
        ]
        f.write(",\n".join(rows))
        f.write("\non conflict (track_id) do update"
                " set parts = excluded.parts, updated_at = now();\n")
    print("OK : %s, %d lignes a charger dans Supabase" % (SEED, len(credits)))


if __name__ == "__main__":
    main()
