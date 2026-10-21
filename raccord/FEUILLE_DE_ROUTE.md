# Raccord : intégration au site osm-music.fr

Feuille de route pour Claude Code. À placer à la racine du dossier du site, avec `raccord-engine.js` et `raccord.html` (le prototype).

## Le but

Un monteur dépose sa séquence vidéo sur osm-music.fr. Raccord trouve tout seul les trois meilleurs titres du catalogue OSM, les cale sur les plans (coupes sur les fins de mesure, fin du morceau sur la dernière image) et fournit l'audio et la cue sheet. Le monteur n'a rien à chercher.

## Ce qui existe déjà

- **Le site** : statique, hébergé sur GitHub Pages (dépôt `V-19str/Original-Scores-Musique`). Il possède une recherche par ambiance avec 17 playlists et leurs synonymes.
- **L'audio** : sur Cloudinary (cloud `dqfogw7sg`, dossier `ORIGINAL SCORES MUSIC - COLLECTIONS - LQ MP3`). Environ 1 450 titres sur 2 560.
- **Le moteur de calage**, `raccord-engine.js`, écrit en JavaScript pur et sans dépendance. Il tourne dans le navigateur comme dans Node :
  - `analyzeSignal(monoFloat32, sampleRate)` produit l'analyse spectrale ;
  - `analyzeRhythm(analyse)` donne le tempo, la grille des mesures, la vraie fin, l'empreinte par mesure et un indice `confidence` (pulsation nette au-dessus d'environ 2, à calibrer) ;
  - `fitTrack(rythme, video)` trouve le meilleur calage ;
  - `renderChannels(...)` fabrique l'audio calé ;
  - `audibleSpan(...)` renvoie le début et la fin audibles.
- **Le prototype** `raccord.html` : interface complète (analyse des plans, frise, lecture synchronisée, export). Il a été conçu pour l'espace Artifacts de Claude, donc son export passe par `claude.use('downloads')`. Sur le site, il faut le remplacer par un téléchargement classique (lien vers un Blob).

## Règles de travail

1. Une branche Git dédiée (`raccord`). Rien ne part sur la branche principale sans l'accord de Vlad.
2. Ne rien casser du site existant. Raccord est une page de plus, plus un dossier de données.
3. Aucun secret dans le dépôt : clés Cloudinary et Anthropic dans un `.env` local, ajouté au `.gitignore`, et dans les variables d'environnement Vercel.
4. Un seul moteur. Le script d'analyse du catalogue et la page web utilisent le même `raccord-engine.js`, sinon les calages ne correspondront pas.
5. Avancer phase par phase, en montrant le résultat à Vlad à la fin de chacune.

---

## Phase 0 : inventaire

- Trouver où le site stocke la liste des titres (fichier JSON ou JS) : identifiant, titre, compositeurs et parts, playlists, lien Cloudinary.
- Lister tous les fichiers présents sur Cloudinary, via l'API Admin en local avec les clés du `.env`.
- Produire un rapport de couverture : titres du catalogue présents sur Cloudinary, titres absents, fichiers Cloudinary sans fiche catalogue.
- **Demander à Vlad** où se trouvent les MP3 des titres absents, et s'il existe des fichiers haute qualité (WAV) pour l'export final.

**Livrable** : `raccord/rapport-couverture.md`, avec le chiffre clé « X titres sur 2 560 utilisables ».

## Phase 1 : compléter Cloudinary

- Écrire un script d'envoi des MP3 manquants, avec la même convention de nommage que l'existant.
- Lancer d'abord un essai à blanc qui affiche ce qui serait envoyé, puis l'envoi réel après validation de Vlad.
- Le script doit pouvoir reprendre là où il s'est arrêté. Mettre à jour le lien Cloudinary dans les données du catalogue.

**Livrable** : couverture proche de 100 %.

## Phase 2 : analyser tout le catalogue, une fois

- Écrire le script Node `raccord/analyse-catalogue.js` :
  - décoder chaque MP3 avec ffmpeg en mono 22 050 Hz (flottant) ;
  - lancer `analyzeSignal` puis `analyzeRhythm` ;
  - enregistrer le résultat.
- Sorties :
  - `raccord/index.json`, un fichier léger d'environ 300 Ko. Une ligne par titre : identifiant, BPM, durée, `confidence`, énergie moyenne, profil d'énergie résumé en 8 valeurs, playlists.
  - `raccord/analyses/<id>.json`, un fichier par titre : grille (`b0`, `barDur`, nombre de mesures), `E`, et pour chaque mesure l'énergie, la brillance et le chroma (12 valeurs quantifiées de 0 à 9, stockées en chaîne compacte).
- Ajouter un rapport : titres à pulsation faible (`confidence` basse) et titres trop courts. Calibrer le seuil de `confidence` en écoutant une dizaine de cas avec Vlad.
- Le script doit pouvoir reprendre, et traiter uniquement les nouveaux titres quand on le relance.

**Livrable** : catalogue entièrement analysé, chaque fichier relu par le moteur sans erreur.

## Phase 3 : le relais « ambiance » sur Vercel

- Créer une petite fonction `/api/ambiance` sur le compte Vercel de Vlad :
  - elle reçoit 6 images de la séquence (JPEG d'environ 512 px de large) ;
  - elle appelle l'API Anthropic avec un modèle Claude récent capable de lire les images (vérifier le nom exact dans la documentation, par exemple `claude-sonnet-5-5`) ;
  - elle renvoie du JSON : `{ ambiances: [...], energie: 0-1, rythme: "lent|moyen|rapide", playlists: [...], mots_cles: [...] }`.
- Envoyer au modèle la liste des 17 playlists et de leurs synonymes, pour qu'il réponde avec le vocabulaire du site.
- Protections :
  - n'accepter que les appels venant d'osm-music.fr ;
  - limiter le nombre d'appels par adresse IP et par jour ;
  - limiter la taille des images ;
  - garder la clé uniquement dans les variables d'environnement Vercel.

**Livrable** : la fonction répond correctement sur 5 séquences test fournies par Vlad.

## Phase 4 : la page Raccord sur le site

Adapter `raccord.html` en `raccord/index.html`, avec la charte du site.

1. Le monteur dépose sa vidéo. La page analyse les plans (code du prototype) et extrait 6 images réparties sur la séquence.
2. Les images partent vers `/api/ambiance`, qui renvoie l'ambiance.
3. Présélection dans `index.json` : correspondance des playlists et mots-clés, rythme cohérent avec la fréquence des plans, durée suffisante. Garder environ 80 candidats.
4. Télécharger les fichiers `analyses/<id>.json` de ces candidats, lancer `fitTrack` sur chacun et garder les 3 meilleurs.
5. Ne charger que ces 3 morceaux depuis Cloudinary, pour l'écoute calée sur l'image. Le monteur doit pouvoir demander d'autres propositions.
6. Export :
   - l'audio calé ;
   - la cue sheet remplie avec les vrais compositeurs et leurs parts, tirés du catalogue.
   - Point à trancher avec Vlad : les MP3 basse qualité ne conviennent pas à une diffusion TV. Il faut soit rendre l'audio depuis les fichiers haute qualité, soit livrer une liste des points de coupe avec un lien vers le fichier haute qualité.
7. Prévoir un plan B si le relais ne répond pas : présélection sur le rythme et l'énergie seulement, avec un message clair pour le monteur.

**Livrable** : la page fonctionne de bout en bout sur une vraie séquence, en moins de 30 secondes entre le dépôt et les 3 propositions.

## Phase 5 : test avec de vrais monteurs

- Recueillir 10 séquences réelles.
- Pour chacune, noter : le classement est-il juste ? la coupe s'entend-elle ? quel morceau le monteur aurait-il choisi ?
- Ajuster les poids du score dans `fitTrack` : coupe, synchro, énergie, rythme.

---

## Ensuite : le plugin Premiere (hors périmètre de cette feuille de route)

Le plugin Premiere réutilisera tel quel :
- `index.json` et le dossier `analyses/` ;
- le relais `/api/ambiance` ;
- `raccord-engine.js`.

Il lira les points de montage directement dans la séquence Premiere, au lieu d'analyser la vidéo, et posera la musique calée sur une piste audio. Deux déclinaisons sont prévues : l'une avec le catalogue OSM, l'autre ouverte à n'importe quelle musique.
