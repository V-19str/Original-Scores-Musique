# Ajout de morceaux depuis l'admin — configuration

Objectif : depuis `admin.html` → section **Ajouter un morceau**, envoyer un MP3
et le voir apparaître sur le site, sans toucher `catalogue.json`.

Le secret API Cloudinary n'est **jamais** dans le code ni sur le site : il vit
dans un **secret Supabase**, utilisé uniquement côté serveur par l'Edge Function
`signer-upload`. Le fichier, lui, ne transite pas par Supabase : le navigateur le
poste directement à Cloudinary avec une signature à durée de vie courte.

Ordre des opérations : 1 → 4. Compter ~10 minutes.

---

## 1. Récupérer les identifiants Cloudinary

1. Aller sur https://console.cloudinary.com → **Settings** → **API Keys**.
2. Relever :
   - **Cloud name** : `dtfm2cwm0` (celui déjà utilisé par tout le catalogue OSM)
   - **API Key** : une suite de chiffres
   - **API Secret** : cliquer sur l'œil pour l'afficher, puis copier.

⚠️ L'API Secret donne un accès complet au compte Cloudinary (upload **et**
suppression). Il ne doit jamais être collé dans un fichier du dépôt.

## 2. Enregistrer les secrets dans Supabase

Dashboard Supabase → projet OSM → **Edge Functions** → **Manage secrets**
(ou **Project Settings → Edge Functions → Secrets**). Ajouter :

| Nom | Valeur | Obligatoire |
|-----|--------|-------------|
| `CLOUDINARY_CLOUD_NAME` | `dtfm2cwm0` | oui |
| `CLOUDINARY_API_KEY` | la clé API de l'étape 1 | oui |
| `CLOUDINARY_API_SECRET` | le secret API de l'étape 1 | oui |
| `CLOUDINARY_FOLDER` | *(laisser vide)* | non |

`CLOUDINARY_FOLDER` vide est volontaire : les nouvelles URLs gardent alors la
même forme que celles du catalogue existant
(`https://res.cloudinary.com/dtfm2cwm0/video/upload/v…/TITRE_ab12cd.mp3`).
Renseigner un dossier (ex. `osm`) range les nouveaux fichiers à part, au prix
d'URLs de forme différente — sans conséquence sur le site, qui lit l'URL
renvoyée par Cloudinary.

En ligne de commande, l'équivalent :

```
supabase secrets set \
  CLOUDINARY_CLOUD_NAME="dtfm2cwm0" \
  CLOUDINARY_API_KEY="…" \
  CLOUDINARY_API_SECRET="…" \
  --project-ref ubpmzncfhkohoyfonjbb
```

## 3. Déployer l'Edge Function

```
supabase functions deploy signer-upload --project-ref ubpmzncfhkohoyfonjbb
```

Sans le CLI : dashboard Supabase → **Edge Functions** → **New function** →
nom `signer-upload` → coller le contenu de
`supabase/functions/signer-upload/index.ts`.

## 4. Appliquer la migration SQL

Dashboard Supabase → **SQL Editor** → coller et exécuter
`supabase/migrations/20260721120000_nouveaux_titres_bpm.sql`.

Elle ajoute la colonne `bpm` à `nouveaux_titres`. Sans elle, l'insertion échoue
(« column bpm does not exist ») et un titre ajouté resterait de toute façon
invisible dans les filtres BPM du site.

La table `nouveaux_titres` elle-même vient de la migration
`20260716130000_plays_et_nouveaux_titres.sql` — si elle n'a jamais été exécutée,
la passer d'abord.

---

## Vérification

1. Ouvrir https://osm-music.fr/admin.html, se connecter.
2. Section **Ajouter un morceau** : choisir un MP3, vérifier le titre
   pré-rempli, choisir une playlist, éventuellement BPM et tags
   (le champ tags propose le vocabulaire déjà utilisé dans le catalogue).
3. **⬆ Envoyer le morceau** → barre de progression, puis
   « ✓ … ajouté à … ».
4. Recharger https://osm-music.fr/ : le titre apparaît dans sa playlist.
   Il est fusionné au catalogue à chaque chargement de page — `catalogue.json`
   n'est pas modifié.

## En cas d'erreur

| Message | Cause |
|---------|-------|
| `Configuration Cloudinary incomplète` | un des trois secrets `CLOUDINARY_*` manque (étape 2) |
| `Accès refusé : réservé à l'administrateur` | session ouverte avec un autre compte que vladimirstreiff@gmail.com |
| `Cloudinary 401` | `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` ne correspondent pas au cloud |
| `Fichier envoyé, mais enregistrement refusé` | la migration de l'étape 4 n'a pas été appliquée |

## Retirer un morceau

Le bouton 🗑 de la liste « Morceaux ajoutés depuis l'admin » supprime la ligne de
`nouveaux_titres` : le titre disparaît du site au chargement suivant. Le fichier
reste chez Cloudinary — volontairement : le navigateur n'a jamais de quoi
supprimer un asset, et un retour arrière ne coûte qu'un ré-ajout. Pour libérer
l'espace, supprimer le fichier depuis la Media Library Cloudinary.
