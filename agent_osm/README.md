# Agent commercial OSM — POC

Outil de prospection musicale semi-automatisée pour Original Scores Music.

## Objectif

Pour chaque prospect (boîte de prod, réalisateur, directeur artistique), l'agent :
1. Identifie les meilleures tracks du catalogue selon ses critères esthétiques
2. Génère un pitch email personnalisé prêt à envoyer

## Structure

```
agent_osm/
├── prospects.json          # Base prospects avec critères de matching
├── match_tracks.py         # Moteur de scoring tracks ↔ prospect
├── pitch_template.md       # Template email français
├── generate_pitch.py       # Orchestrateur principal
└── pitchs_generes/         # Emails générés (un .md par prospect)
```

## Usage

```bash
# Générer tous les pitchs pour les prospects "a_contacter"
python3 agent_osm/generate_pitch.py

# Tester le matching pour un prospect
python3 agent_osm/match_tracks.py
```

## Schéma des tags catalogue

Chaque track possède un tableau `tags` avec :
- **Mode** : `majeur`, `mineur`
- **Tonalité complète** : `do majeur`, `ré mineur`, `la mineur`, etc.
- **Tempo** : `lent`, `modéré`, `rapide`, `très rapide`
- **Énergie** : `haute énergie`, `énergie moyenne`, `basse énergie`
- **Fréquences** : `graves`, `équilibré`, `aigus`
- **Ambiance** : `sombre`, `lumineux`, `mélancolique`, `joyeux`, `festif`,
  `positif`, `puissant`, `épique`, `intense`, `dramatique`, `tendu`, `calme`, `énergique`

Plus un champ `bpm` (entier).

## Statuts prospect

- `a_contacter` — inclus dans la prochaine génération
- `contacte` — pitch envoyé, en attente de réponse
- `en_discussion` — échange en cours
- `client` — licence signée
- `hors_cible` — ne pas recontacter
