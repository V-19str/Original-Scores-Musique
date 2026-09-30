# Installation du panneau OSM pour Adobe Premiere Pro

## Développement (test local)

### 1. Activer le mode debug CEP

**Windows** (PowerShell en admin) :
```
reg add "HKEY_CURRENT_USER\SOFTWARE\Adobe\CSXS.12" /v PlayerDebugMode /t REG_SZ /d 1 /f
```
*(Remplacer `12` par la version de votre Creative Cloud : 11 pour CC 2021, 12 pour CC 2022, 13 pour 2023+)*

**macOS** (Terminal) :
```
defaults write com.adobe.CSXS.12 PlayerDebugMode 1
```

### 2. Copier le dossier d'extension

Copier **l'intégralité du dossier `premiere-extension/`** dans :

| Système | Chemin |
|---------|--------|
| Windows | `C:\Users\<nom>\AppData\Roaming\Adobe\CEP\extensions\osm-panel\` |
| macOS   | `~/Library/Application Support/Adobe/CEP/extensions/osm-panel/` |

Le dossier doit contenir `CSXS/manifest.xml`, `index.html`, `js/`, `css/`, `jsx/`.

### 3. Ouvrir le panneau dans Premiere Pro

Menu **Fenêtre → Extensions → OSM — Original Scores Music**

---

## Distribution (Adobe Exchange)

1. Créer un compte sur [Adobe Exchange](https://exchange.adobe.com/creativecloud/add-ons)
2. Soumettre le dossier `premiere-extension/` zippé comme extension CEP
3. Les monteurs installent via **Fenêtre → Exchange** dans Premiere

---

## Fonctionnement

- Charge le catalogue OSM depuis osm-music.fr au démarrage
- Recherche par titre, playlist ou ambiance
- Préecoute audio directement dans le panneau
- **Importer** télécharge le fichier audio et l'insère dans le projet/séquence Premiere
- La connexion OSM (optionnelle) déverrouille les données compositeurs pour les cue sheets SACEM
