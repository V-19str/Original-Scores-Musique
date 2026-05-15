# Vocabulaire du catalogue OSM
*Généré le 2026-05-15 — 2 564 tracks, 2 553 avec BPM*

---

## Ambiance (16 valeurs)

| Tag | Occurrences |
|---|---:|
| sombre | 971 |
| lumineux | 683 |
| mélancolique | 568 |
| festif | 537 |
| énergique | 537 |
| joyeux | 537 |
| positif | 437 |
| puissant | 418 |
| épique | 418 |
| intense | 355 |
| dramatique | 355 |
| tendu | 355 |
| calme | 246 |
| doux | 19 |
| introspectif | 15 |
| contemplatif | 15 |

---

## Énergie (3 valeurs)

| Tag | Occurrences |
|---|---:|
| haute énergie | 1 580 |
| énergie moyenne | 903 |
| faible énergie | 78 |

**Mapping prospects.json → tag catalogue :**
- `"haute"` → `haute énergie`
- `"moyenne"` → `énergie moyenne`
- `"basse"` → `faible énergie`  *(alias conservé dans ENERGIE_MAP)*

---

## Tempo (5 valeurs)

| Tag | Occurrences |
|---|---:|
| rapide | 926 |
| modéré | 907 |
| très rapide | 514 |
| lent | 158 |
| très lent | 56 |

---

## Tonalité — mode (2 valeurs)

| Tag | Occurrences |
|---|---:|
| mineur | 1 341 |
| majeur | 1 220 |

---

## Tonalité complète (24 valeurs)

| Tag | Occurrences |
|---|---:|
| la mineur | 299 |
| do majeur | 291 |
| ré mineur | 259 |
| ré majeur | 182 |
| mi mineur | 176 |
| sol majeur | 173 |
| la majeur | 159 |
| do mineur | 143 |
| sol mineur | 131 |
| mi majeur | 98 |
| fa mineur | 84 |
| fa majeur | 84 |
| do# mineur | 65 |
| si mineur | 51 |
| la# majeur | 47 |
| do# majeur | 46 |
| fa# mineur | 44 |
| sol# majeur | 42 |
| si majeur | 36 |
| ré# majeur | 35 |
| la# mineur | 33 |
| ré# mineur | 31 |
| fa# majeur | 27 |
| sol# mineur | 25 |

---

## Fréquences (3 valeurs)

| Tag | Occurrences |
|---|---:|
| graves | 2 126 |
| équilibré | 413 |
| aigus | 22 |

---

## Distribution BPM

| Stat | Valeur |
|---|---:|
| minimum | 31 |
| percentile 25 | 96 |
| **médiane (p50)** | **112** |
| percentile 75 | 129 |
| maximum | 235 |
| moyenne | 115,8 |
| écart-type | 31,6 |

La majorité des tracks se situe entre **96 et 129 BPM**.

---

## Notes pour les critères prospects

- `contemplatif` et `introspectif` existent mais sont rares (15 occurrences chacun) — les combiner avec `mélancolique` ou `calme` pour élargir le matching.
- `faible énergie` est rare (78) — utiliser `énergie moyenne` comme critère principal pour les documentaires calmes.
- `très rapide` (514) dépasse `lent` (158) — le catalogue est dominé par des tempos élevés.
- `graves` est omniprésent (2 126 / 2 564) — peu discriminant, à éviter comme critère unique.
