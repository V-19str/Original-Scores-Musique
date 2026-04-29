@echo off
chcp 65001 >nul
title OSM — Installation et analyse audio

echo.
echo  ╔════════════════════════════════════════╗
echo  ║   OSM — Analyse audio automatique     ║
echo  ╚════════════════════════════════════════╝
echo.

:: Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ❌ Python n'est pas installé.
    echo     Télécharge Python sur https://python.org
    echo     Coche bien "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)

echo  ✓ Python trouvé
echo.
echo  📦 Installation des bibliothèques nécessaires...
echo.

pip install librosa numpy requests --quiet

echo.
echo  ✓ Bibliothèques installées
echo.
echo  🎵 Lancement de l'analyse...
echo     (Le script peut s'interrompre et reprendre — il se souvient où il en est)
echo.

python analyze_local.py

pause
