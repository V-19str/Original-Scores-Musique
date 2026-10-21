# Raccord

Feuille de route : `FEUILLE_DE_ROUTE.md`. Moteur unique : `raccord-engine.js` (page web et script Node).

## Fichiers

- `analyse-catalogue.js` : Phase 2. `node raccord/analyse-catalogue.js` (reprenable ; `--limit N`, `--force`, `--ids a,b`). Demande `ffmpeg`. Produit `index.json`, `analyses/<id>.json`, `rapport-analyse.md`.
- `analysis-format.js` : codage compact des analyses, partagé script et page.
- `index.html` + `config.js` : la page. Mettre l'URL réelle du relais dans `config.js`.
- `relais/` : Phase 3, fonction Vercel `/api/ambiance`. À déployer comme projet Vercel séparé (le site est sur GitHub Pages), racine du projet = `raccord/relais`.

## Relais : variables d'environnement Vercel

`ANTHROPIC_API_KEY` (obligatoire), `ANTHROPIC_MODEL` (défaut `claude-sonnet-5-5`), `ALLOWED_ORIGINS`, `DAILY_LIMIT` (défaut 30 appels par IP et par jour), `KV_REST_API_URL` et `KV_REST_API_TOKEN` (quota partagé entre instances, sinon repli en mémoire). Aucune clé dans le dépôt.

## Reste à faire

- Lancer l'analyse sur le vrai catalogue (accès Cloudinary requis) et calibrer le seuil `confidence`.
- Cue sheet : brancher les compositeurs et parts depuis Supabase (le champ est à saisir pour l'instant).
- Export haute qualité : décision de Vlad (rendu WAV ou liste de points de coupe).
