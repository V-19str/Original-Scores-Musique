# Rapport déduplication — catalogue OSM
*Généré le 2026-05-15*

---

## Chiffres clés

| Métrique | Valeur |
|---|---:|
| Tracks totales dans catalogue.json | **2 564** |
| Groupes de doublons (Règle A) | 769 |
| Doublons supprimés (Règle A) | 1 392 |
| Groupes de doublons (Règle B) | 769 |
| Doublons supprimés (Règle B) | 1 395 |
| **Tracks uniques après dédup** | **1 169** |
| Taux de duplication | 54 % |

---

## Règles appliquées

**Règle A — doublon certain**  
Même titre nettoyé + même BPM + même tonalité complète.  
→ 769 groupes, 1 392 doublons.

**Règle B — doublon probable**  
Même titre nettoyé (BPM et tags peuvent varier).  
→ 769 groupes, 1 395 doublons.

**Écart A ↔ B** : seulement **3 tracks** ont le même titre mais un BPM différent (variations légères d'une version à l'autre). Les deux règles convergent quasi-totalement.

**Conclusion** : les doublons sont structurels — chaque track est distribuée dans plusieurs playlists thématiques (ex. *Desillusion* → Action, Divers, Paranormal, Romance, Électro, Électro-Pop). Ce n'est pas une erreur de saisie mais une organisation éditoriale.

---

## 5 exemples de groupes de doublons

### 1. Yoga Project Vv — 7 occurrences
- **Playlists** : Atmosphère · Groovy · Piano · Swing Jazz · World Music · Électro · Électro-Pop
- **BPM** : 144 | **Tonalité** : mi mineur

### 2. Desillusion — 6 occurrences
- **Playlists** : Action · Divers · Paranormal · Romance · Électro · Électro-Pop
- **BPM** : 129 | **Tonalité** : sol majeur

### 3. Fly In The Motor — 6 occurrences
- **Playlists** : Atmosphère · Divers · Folk Acoustique · Pop Acoustique · Romance · Électro-Pop
- **BPM** : 89 | **Tonalité** : ré mineur

### 4. Fly In The Motor Only Percs — 6 occurrences
- **Playlists** : Atmosphère · Divers · Folk Acoustique · Pop Acoustique · Romance · Électro-Pop
- **BPM** : 89 | **Tonalité** : ré mineur

### 5. Fly In The Motor Piano Only — 6 occurrences
- **Playlists** : Atmosphère · Divers · Folk Acoustique · Pop Acoustique · Romance · Électro-Pop
- **BPM** : 60 | **Tonalité** : sol majeur

---

## Fichier produit

`agent_osm/catalogue_unique.json` — 1 169 tracks canoniques.  
Chaque track canonique conserve un champ `"playlists": [...]` listant toutes ses playlists d'origine.  
Le champ `"playlist"` (singulier) reste celui de la première occurrence.
