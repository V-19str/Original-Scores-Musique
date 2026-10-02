# Rapport de couverture : Phase 0 (hors ligne)

Généré depuis `catalogue.json` seul. **L'API Admin Cloudinary n'a pas pu être interrogée** : pas de clés dans cette session et le réseau vers Cloudinary est bloqué. La couverture réelle reste donc à confirmer en local (voir « À faire »).

## Chiffres clés

- Titres au catalogue : **2564** (champ `total` : 2564)
- Titres avec un lien Cloudinary : **2564** sur 2564
- Cloud utilisé par les liens : {'dtfm2cwm0': 2564}
- Identifiants en double : 0 ; liens en double : 0
- Lien qui ne finit pas par `<id>.mp3` : 4
- Durée illisible : 4 ; titres de moins de 45 s : 113
- Titres sans BPM : 11
- Playlists distinctes sur les titres : 29 (la liste `playlists` en contient 29)

## Écarts avec la feuille de route

1. **Cloud name** : la feuille de route indique `dqfogw7sg` ; tous les liens du catalogue et les scripts (`fetch_catalogue.py`, workflow, fonction Supabase) utilisent `dtfm2cwm0`. À confirmer avec Vlad.
2. **Le catalogue actuel référence déjà 2 564 liens Cloudinary**, alors que la feuille de route parle de ~1 450 titres en ligne sur 2 560. Soit `fetch_catalogue.py` ne liste que les fichiers présents (donc la Phase 1 serait déjà faite), soit des liens pointent vers des fichiers absents. Seul un contrôle réel le dira.
3. **Compositeurs et parts** : `credits.json` est volontairement hors dépôt (Supabase, RLS) ; la cue sheet de Raccord devra les lire côté Supabase, pas dans les fichiers statiques.
4. `catalogue.json` figure dans `.gitignore` tout en étant suivi par Git.
5. Le catalogue a déjà un `bpm` pour 2553 titres (script `analyze_local.py`) : à comparer avec celui du moteur Raccord en Phase 2.

## Répartition par playlist

- Divers : 472
- Atmosphère : 381
- Électro-Pop : 219
- Action : 177
- Folk Acoustique : 99
- Orchestral : 99
- Paranormal : 99
- Piano : 99
- Romance : 99
- Suspense : 99
- World Music : 99
- Électro : 99
- Pizzicato : 98
- Pop Acoustique : 94
- Ludique : 85
- Burlesque : 52
- Rock : 50
- Groovy : 26
- Swing Jazz : 22
- Country Blues : 21
- Neutre Positif : 12
- Paname : 12
- Reggae : 11
- Hard Rock : 10
- Latino : 9
- Mélancolie : 6
- Transition : 6
- Loops : 5
- samples : 4

## À faire (en local, avec les clés Cloudinary dans `.env`)

1. `python fetch_catalogue.py` pour lister les fichiers Cloudinary (API Admin), puis comparer aux 2 564 fiches : absents, orphelins.
2. À défaut de clés : un contrôle HEAD sur chaque lien du catalogue donne le même résultat.

## Questions pour Vlad

- Quel cloud est le bon, `dtfm2cwm0` ou `dqfogw7sg` ?
- Où sont les MP3 des titres absents, s'il y en a ?
- Existe-t-il des WAV haute qualité pour l'export final ?
