#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-rendu SEO des playlists OSM.

Genere une page HTML statique par playlist dans playlists/, plus une page
sommaire, et reinjecte les URLs dans sitemap.xml.

Pourquoi : index.html est une application monopage qui construit tout le
catalogue en JavaScript apres un fetch de catalogue.json. Les moteurs voient
donc une page quasi vide, et aucun des 2 560 titres n'est indexable. Les pages
generees ici portent les titres en HTML brut, un JSON-LD MusicPlaylist et un
canonical, et renvoient vers le lecteur reel via /?playlist=<label>.

Sources de verite, jamais dupliquees :
  - catalogue.json  : les titres (id, titre, duree, BPM, tags)
  - index.html      : le bloc THEMES (libelle, genres, description, photo,
                      couleur de chaque playlist), lu par extraction

Utilisation :
    python build_playlists.py            # genere playlists/ + met a jour sitemap.xml
    python build_playlists.py --check     # n'ecrit rien, affiche ce qui changerait

Relancer apres chaque mise a jour de catalogue.json (fetch_catalogue.py).
"""

import argparse
import io
import json
import os
import re
import sys
import unicodedata
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.path.join(ROOT, "catalogue.json")
INDEX = os.path.join(ROOT, "index.html")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
OUT_DIR = os.path.join(ROOT, "playlists")

SITE = "https://osm-music.fr"
OG_IMAGE = SITE + "/osm_linkedin_banner.png"

# `samples` est deja exclu cote site (index.html filtre cette playlist) : elle
# n'a pas de page publique, donc pas de page SEO non plus.
EXCLUDED = {"samples"}


# ---------------------------------------------------------------- utilitaires

def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def write(path, content):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def slugify(label):
    """« Électro-Pop » -> « electro-pop ». Sert de nom de fichier et d'URL."""
    ascii_ = unicodedata.normalize("NFD", label)
    ascii_ = "".join(c for c in ascii_ if unicodedata.category(c) != "Mn")
    ascii_ = ascii_.lower().replace("&", " et ")
    ascii_ = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")
    return ascii_ or "playlist"


def esc(s):
    """Echappement HTML. Les titres du catalogue viennent de noms de fichiers,
    mais rien ne garantit qu'ils resteront exempts de & ou de chevrons."""
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def iso_duration(mmss):
    """« 2:03 » -> « PT2M3S », attendu par schema.org. Chaine vide si inconnu."""
    if not mmss or mmss == "0:00":
        return ""
    parts = mmss.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return ""
    if len(nums) == 2:
        h, m, s = 0, nums[0], nums[1]
    elif len(nums) == 3:
        h, m, s = nums
    else:
        return ""
    out = "PT"
    if h:
        out += "%dH" % h
    if m or h:
        out += "%dM" % m
    return out + "%dS" % s


def truncate(text, limit=155):
    """Description meta : une phrase entiere si possible, jamais un mot coupe."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    dot = cut.rfind(". ")
    if dot > limit * 0.5:
        return cut[:dot + 1]
    return cut[:cut.rfind(" ")].rstrip(",;:") + "…"


# ------------------------------------------------- extraction des metadonnees

# Le bloc THEMES d'index.html est la seule description editoriale des playlists.
# Le relire ici evite d'en maintenir une deuxieme copie qui divergerait au
# premier ajustement de texte.

THEME_RE = re.compile(r'\{label:"([^"]+)",playlists:\[')
PLAYLIST_RE = re.compile(
    r'\{key:"(?P<key>[^"]*)",'
    r'label:"(?P<label>[^"]*)",'
    r'color:"(?P<color>[^"]*)",'
    r'photo:"(?P<photo>[^"]*)",'
    r'genres:"(?P<genres>[^"]*)",'
    r'desc:"(?P<desc>[^"]*)",'
    r'tags:\[(?P<tags>[^\]]*)\]\}'
)


def parse_themes(html):
    """Renvoie (infos par label, ordre des themes) depuis le bloc THEMES."""
    start = html.find("const THEMES=[")
    if start == -1:
        sys.exit("Bloc THEMES introuvable dans index.html — format modifié ?")
    end = html.find("const PLAYLIST_MAP", start)
    block = html[start:end if end != -1 else len(html)]

    infos, themes = {}, []
    # Le bloc est plat : on avance en parallele sur les entetes de theme et sur
    # les playlists, chaque playlist appartenant au dernier theme rencontre.
    marks = sorted(
        [(m.start(), "theme", m) for m in THEME_RE.finditer(block)] +
        [(m.start(), "playlist", m) for m in PLAYLIST_RE.finditer(block)]
    )
    current = None
    for _, kind, m in marks:
        if kind == "theme":
            current = {"label": m.group(1), "playlists": []}
            themes.append(current)
            continue
        tags = re.findall(r'"([^"]*)"', m.group("tags"))
        info = {
            "label": m.group("label"),
            "color": m.group("color"),
            "photo": m.group("photo"),
            "genres": m.group("genres"),
            "desc": m.group("desc"),
            "tags": tags,
        }
        infos[info["label"]] = info
        if current:
            current["playlists"].append(info["label"])
    return infos, themes


# ------------------------------------------------------------------- rendu

CSS = """*{box-sizing:border-box;margin:0;padding:0}
:root{--red:#FF5500;--bg:#f6f6f6;--bg2:#eeeeee;--bg3:#e4e4e4;--text:#111;--muted:#666;--border:rgba(0,0,0,0.1);--card:#fff}
[data-theme="dark"]{--bg:#141414;--bg2:#1f1f1f;--bg3:#2a2a2a;--text:#fff;--muted:#b0b0b0;--border:rgba(255,255,255,0.12);--card:#111}
[data-theme="creme"]{--bg:#f4ecd8;--bg2:#efe5cd;--bg3:#e8dbbe;--text:#3a2e1a;--muted:#8a755a;--border:rgba(90,70,40,0.16);--card:#fbf5e6}
[data-theme="nuit"]{--bg:#0d1b2a;--bg2:#152536;--bg3:#1d3149;--text:#eaf2fb;--muted:#8ba4bc;--border:rgba(130,170,210,0.16);--card:#0f2033}
body{background:var(--bg);color:var(--text);font-family:'Montserrat',system-ui,sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit}
header{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--border);padding:0 24px;height:60px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none}
.logo-mark{background:linear-gradient(135deg,#FF5500,#FF006E);color:#fff;font-size:12px;font-weight:700;letter-spacing:2px;padding:5px 8px;border-radius:3px}
.logo-name{font-size:13px;font-weight:600;letter-spacing:2px}
.head-links{display:flex;gap:6px;flex-wrap:wrap}
.head-links a{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--muted);text-decoration:none;padding:8px 12px;border-radius:4px}
.head-links a:hover{color:var(--text);background:var(--bg3)}
main{max-width:1000px;margin:0 auto;padding:32px 24px 64px}
.crumb{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:18px}
.crumb a{text-decoration:none}
.crumb a:hover{color:var(--text)}
.hero{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;margin-bottom:14px}
.hero-cover{width:180px;height:180px;border-radius:8px;background-size:cover;background-position:center;flex-shrink:0;border:1px solid var(--border)}
.hero-body{flex:1;min-width:260px}
h1{font-size:38px;font-weight:900;letter-spacing:-0.5px;line-height:1.1;margin-bottom:8px}
.genres{font-size:12px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent);margin-bottom:12px}
.desc{color:var(--muted);max-width:62ch;margin-bottom:14px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.tag{font-size:11px;color:var(--muted);background:var(--bg3);border-radius:11px;padding:3px 10px}
.cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:12px 22px;border-radius:5px}
.cta:hover{filter:brightness(1.1)}
.count{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin:34px 0 10px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden}
th{font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);text-align:left;padding:10px 14px;border-bottom:1px solid var(--border)}
td{padding:9px 14px;border-bottom:1px solid var(--border);font-size:14px}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--bg2)}
.num{color:var(--muted);font-size:12px;width:44px}
.dur,.bpm{color:var(--muted);font-size:12px;white-space:nowrap;text-align:right;width:78px}
.others{margin-top:44px}
.others h2{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.pl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.pl-card{display:block;text-decoration:none;background:var(--card);border:1px solid var(--border);border-radius:7px;padding:13px 15px}
.pl-card:hover{border-color:var(--muted)}
.pl-card strong{display:block;font-size:14px;font-weight:600;margin-bottom:3px}
.pl-card span{font-size:11px;color:var(--muted)}
footer{border-top:1px solid var(--border);padding:26px 24px;text-align:center;font-size:11px;color:var(--muted)}
footer a{color:var(--muted)}
@media(max-width:640px){h1{font-size:28px}.hero-cover{width:120px;height:120px}main{padding:24px 16px 48px}.bpm{display:none}th.bpm{display:none}}
"""

# La page ne charge aucun script applicatif : seule cette ligne restitue le
# theme choisi sur le site, pour ne pas repasser en clair au clic depuis
# index.html. Tout le reste est du HTML servi tel quel aux moteurs.
THEME_SCRIPT = ("(function(){var t=localStorage.getItem('osm-theme')||'light';"
                "document.documentElement.setAttribute('data-theme',t);})();")

HEAD_LINKS = [
    ("/", "Catalogue"),
    ("/playlists/", "Playlists"),
    ("/service.html", "Services"),
    ("/television.html", "Télévision"),
    ("/qui-sommes-nous.html", "Qui sommes-nous"),
]


def head_html(title, description, canonical, image, extra_ld=""):
    links = "".join(
        '<a href="%s">%s</a>' % (esc(u), esc(t)) for u, t in HEAD_LINKS)
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<meta name="theme-color" content="#FF5500">
<link rel="canonical" href="%(canonical)s">
<meta property="og:type" content="website">
<meta property="og:url" content="%(canonical)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:image" content="%(image)s">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%(title)s">
<meta name="twitter:description" content="%(desc)s">
<meta name="twitter:image" content="%(image)s">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
<script>%(theme)s</script>
<style>%(css)s</style>
%(ld)s
</head>
<body>
<header>
  <a class="logo" href="/"><span class="logo-mark">OSM</span><span class="logo-name">ORIGINAL SCORES MUSIC</span></a>
  <nav class="head-links">%(links)s</nav>
</header>
""" % {
        "title": esc(title), "desc": esc(description), "canonical": esc(canonical),
        "image": esc(image), "theme": THEME_SCRIPT, "css": CSS,
        "ld": extra_ld, "links": links,
    }


def footer_html():
    return """<footer>
  <p>© Original Scores Music — musique originale pour l'image.
  <a href="/">Écouter le catalogue</a> ·
  <a href="/inscription.html">Demander un accès</a> ·
  <a href="/qui-sommes-nous.html">Qui sommes-nous</a></p>
</footer>
</body>
</html>
"""


def jsonld(obj):
    return ('<script type="application/ld+json">%s</script>'
            % json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def render_playlist(info, tracks, others):
    label = info["label"]
    slug = slugify(label)
    url = "%s/playlists/%s.html" % (SITE, slug)
    genres_short = info["genres"].split(" · ")[0] if info["genres"] else label
    title = "%s — musique %s libre de droits pour l'image | OSM" % (label, genres_short.lower())
    description = truncate(info["desc"])

    # MusicPlaylist : chaque titre est une entree indexable, avec sa duree.
    # `url` pointe vers le lecteur, pas vers le MP3 : le fichier n'est
    # telechargeable que par un client identifie.
    ld_tracks = []
    for t in tracks:
        entry = {
            "@type": "MusicRecording",
            "name": t.get("title", ""),
            "url": "%s/?playlist=%s#%s" % (SITE, slug, t.get("id", "")),
        }
        dur = iso_duration(t.get("duration"))
        if dur:
            entry["duration"] = dur
        ld_tracks.append(entry)

    ld = jsonld({
        "@context": "https://schema.org",
        "@type": "MusicPlaylist",
        "@id": url,
        "name": "%s — Original Scores Music" % label,
        "url": url,
        "description": info["desc"],
        "numTracks": len(tracks),
        "genre": [g.strip() for g in info["genres"].split("·")] if info["genres"] else [],
        "keywords": ", ".join(info["tags"]),
        "image": info["photo"],
        "author": {"@type": "Organization", "name": "Original Scores Music", "url": SITE + "/"},
        "track": ld_tracks,
    }) + jsonld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Playlists", "item": SITE + "/playlists/"},
            {"@type": "ListItem", "position": 3, "name": label, "item": url},
        ],
    })

    rows = []
    for i, t in enumerate(tracks, 1):
        bpm = t.get("bpm")
        rows.append(
            '<tr><td class="num">%d</td><td>%s</td><td class="dur">%s</td><td class="bpm">%s</td></tr>'
            % (i, esc(t.get("title", "")), esc(t.get("duration") or "—"),
               ("%s BPM" % bpm) if bpm else "—"))

    cards = "".join(
        '<a class="pl-card" href="/playlists/%s.html"><strong>%s</strong><span>%s titre%s</span></a>'
        % (slugify(o["label"]), esc(o["label"]), o["count"], "s" if o["count"] > 1 else "")
        for o in others)

    body = """<main style="--accent:%(color)s">
  <p class="crumb"><a href="/">Accueil</a> › <a href="/playlists/">Playlists</a> › %(label)s</p>
  <div class="hero">
    <div class="hero-cover" style="background-image:url('%(photo)s')"></div>
    <div class="hero-body">
      <h1>%(label)s</h1>
      <p class="genres">%(genres)s</p>
      <p class="desc">%(desc)s</p>
      <div class="tags">%(tags)s</div>
      <a class="cta" href="/?playlist=%(slug)s">▶ Écouter les %(count)d titres</a>
    </div>
  </div>

  <p class="count">%(count)d titres dans cette playlist</p>
  <table>
    <thead><tr><th>#</th><th>Titre</th><th class="dur">Durée</th><th class="bpm">Tempo</th></tr></thead>
    <tbody>%(rows)s</tbody>
  </table>

  <section class="others">
    <h2>Autres playlists</h2>
    <div class="pl-grid">%(cards)s</div>
  </section>
</main>
""" % {
        "color": esc(info["color"] or "#FF5500"),
        "label": esc(label),
        "photo": esc(info["photo"]),
        "genres": esc(info["genres"]),
        "desc": esc(info["desc"]),
        "tags": "".join('<span class="tag">%s</span>' % esc(t) for t in info["tags"]),
        "slug": slug,
        "count": len(tracks),
        "rows": "".join(rows),
        "cards": cards,
    }

    return head_html(title, description, url, info["photo"] or OG_IMAGE, ld) + body + footer_html()


def render_index(themes, counts, infos, total):
    url = SITE + "/playlists/"
    title = "Les %d playlists du catalogue OSM | Original Scores Music" % len(counts)
    description = ("Les %d univers musicaux d'Original Scores Music : %s titres "
                   "originaux pour le cinéma, la télévision et la publicité."
                   % (len(counts), total))

    ld = jsonld({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": url,
        "name": title,
        "url": url,
        "description": description,
        "hasPart": [
            {
                "@type": "MusicPlaylist",
                "name": label,
                "url": "%s/playlists/%s.html" % (SITE, slugify(label)),
                "numTracks": counts[label],
            }
            for label in counts
        ],
    })

    sections = []
    for theme in themes:
        cards = "".join(
            '<a class="pl-card" href="/playlists/%s.html"><strong>%s</strong><span>%s · %d titres</span></a>'
            % (slugify(label), esc(label), esc(infos[label]["genres"].split(" · ")[0]), counts[label])
            for label in theme["playlists"] if label in counts)
        if not cards:
            continue
        sections.append('<section class="others"><h2>%s</h2><div class="pl-grid">%s</div></section>'
                        % (esc(theme["label"]), cards))

    body = """<main style="--accent:#FF5500">
  <p class="crumb"><a href="/">Accueil</a> › Playlists</p>
  <h1>Les %(n)d playlists OSM</h1>
  <p class="desc" style="margin-top:10px">%(desc)s</p>
  <a class="cta" href="/">▶ Ouvrir le catalogue</a>
  %(sections)s
</main>
""" % {"n": len(counts), "desc": esc(description), "sections": "".join(sections)}

    return head_html(title, description, url, OG_IMAGE, ld) + body + footer_html()


# ------------------------------------------------------------------ sitemap

SITEMAP_ENTRY = """
  <url>
    <loc>%s</loc>
    <lastmod>%s</lastmod>
    <changefreq>%s</changefreq>
    <priority>%s</priority>
  </url>
"""


def update_sitemap(labels, today):
    """Remplace le bloc /playlists/ du sitemap, laisse le reste intact."""
    xml = read(SITEMAP)
    # Les entrees generees precedemment sont retirees d'abord : relancer le
    # script deux fois de suite ne doit pas dupliquer les URLs.
    xml = re.sub(r"\n?  <url>\s*<loc>[^<]*/playlists/[^<]*</loc>.*?</url>\n?",
                 "\n", xml, flags=re.S)
    xml = re.sub(r"\n{3,}", "\n\n", xml)

    entries = SITEMAP_ENTRY % (SITE + "/playlists/", today, "weekly", "0.8")
    for label in labels:
        entries += SITEMAP_ENTRY % (
            "%s/playlists/%s.html" % (SITE, slugify(label)), today, "monthly", "0.7")

    return xml.replace("</urlset>", entries.lstrip("\n") + "\n</urlset>")


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Pre-rendu SEO des playlists OSM.")
    parser.add_argument("--check", action="store_true",
                        help="n'ecrit rien, affiche seulement ce qui changerait")
    args = parser.parse_args()

    catalogue = json.loads(read(CATALOGUE))
    infos, themes = parse_themes(read(INDEX))

    # Les titres ajoutes depuis l'admin vivent dans Supabase (nouveaux_titres)
    # et sont fusionnes cote client : ils n'apparaissent donc pas ici tant que
    # catalogue.json n'a pas ete regenere. Ce n'est pas un probleme pour le SEO
    # (une page se recalcule a chaque build), mais ca explique un ecart de
    # comptage entre la page publique et la page pre-rendue.
    by_playlist = {}
    for t in catalogue.get("tracks", []):
        pl = t.get("playlist")
        if not pl or pl in EXCLUDED:
            continue
        by_playlist.setdefault(pl, []).append(t)

    missing = [pl for pl in by_playlist if pl not in infos]
    if missing:
        print("! Playlists du catalogue absentes du bloc THEMES, ignorees : %s"
              % ", ".join(sorted(missing)))
        for pl in missing:
            del by_playlist[pl]

    # Ordre des themes d'index.html, pour que les pages et le sommaire suivent
    # la meme progression que le site.
    ordered = [label for theme in themes for label in theme["playlists"] if label in by_playlist]
    counts = {label: len(by_playlist[label]) for label in ordered}
    total = sum(counts.values())

    if not args.check:
        os.makedirs(OUT_DIR, exist_ok=True)

    today = date.today().isoformat()
    written = 0
    for label in ordered:
        tracks = sorted(by_playlist[label], key=lambda t: (t.get("title") or "").lower())
        others = [{"label": o, "count": counts[o]} for o in ordered if o != label]
        html = render_playlist(infos[label], tracks, others)
        path = os.path.join(OUT_DIR, slugify(label) + ".html")
        if args.check:
            print("  %-20s %4d titres  ->  playlists/%s.html" % (label, len(tracks), slugify(label)))
        else:
            write(path, html)
        written += 1

    index_path = os.path.join(OUT_DIR, "index.html")
    if not args.check:
        write(index_path, render_index(themes, counts, infos, total))
        write(SITEMAP, update_sitemap(ordered, today))

    print("%s %d pages playlists + 1 sommaire, %d titres au total."
          % ("[check]" if args.check else "OK :", written, total))
    if not args.check:
        print("OK : sitemap.xml, %d URLs /playlists/ reinjectees." % (written + 1))


if __name__ == "__main__":
    main()
