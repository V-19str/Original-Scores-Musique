#!/usr/bin/env python3
"""
Test rapide de analyze_v2 sur 5 morceaux — valider avant de lancer les 2560.
Lance : python test_v2.py
"""

import json, sys
from pathlib import Path

try:
    import requests, numpy as np, librosa
except ImportError:
    print("❌ pip install librosa requests numpy")
    sys.exit(1)

# Importer les fonctions de analyze_v2
sys.path.insert(0, str(Path(__file__).parent))
from analyze_v2 import analyze_v2, CACHE_DIR

BASE      = Path(__file__).parent
CATALOGUE = BASE / 'catalogue.json'

with open(CATALOGUE, encoding='utf-8') as f:
    tracks = json.load(f)['tracks']

# Prendre 5 morceaux variés (1 sur 500)
samples = [tracks[i] for i in [0, 500, 1000, 1500, 2000] if i < len(tracks)]

print(f"\n🧪 TEST analyze_v2 — {len(samples)} morceaux\n")
print(f"{'Titre':<40} {'Tags existants':<35} {'Nouveaux tags'}")
print("─" * 110)

for t in samples:
    existing = t.get('tags', [])
    try:
        new_tags = analyze_v2(t['url'], existing)
        new_str  = ' · '.join(new_tags) if new_tags else '(rien de nouveau)'
        ex_str   = ' · '.join(existing[:4]) + ('…' if len(existing) > 4 else '')
        print(f"{t['title'][:39]:<40} {ex_str:<35} {new_str}")
    except Exception as e:
        print(f"{t['title'][:39]:<40} {'ERREUR':<35} {str(e)[:50]}")

print(f"\n✅ Test terminé. Si les nouveaux tags semblent cohérents, lance analyze_v2.py\n")
input("Appuie sur Entrée pour fermer...")
