# Statut Admin — OSM
*Diagnostic du 2026-05-15*

---

## Pages admin trouvées

| Fichier | Taille | Branche | Statut |
|---|---|---|---|
| `admin.html` | 545 lignes | **main uniquement** | Déployé sur osm-music.fr |
| `login.html` | ~100 lignes | toutes branches | Déployé sur osm-music.fr |
| `login-monteurs.html` | ~544 lignes | toutes branches | Déployé sur osm-music.fr |

---

## admin.html — détail

### URL publique
```
https://osm-music.fr/admin.html
```

### Authentification
- **Type :** compte Supabase (email + mot de passe)
- **Backend :** Supabase `auth.signInWithPassword()` — pas de mot de passe en dur côté client
- **Double protection :**
  1. Login Supabase obligatoire (email + mdp)
  2. Mot de passe admin secondaire `OSM_ADMIN_2026` pour déclencher la vue données via une fonction Postgres RLS-contournante
- **Statut :** Propre (pas de credential exposé dans le JS, tout passe par Supabase)

### Connexion Supabase
```
SUPABASE_URL = https://ubpmzncfhkohoyfonjbb.supabase.co
SUPABASE_KEY = sb_publishable_… (clé anon/publique — OK de laisser dans le JS)
```

---

## Problème d'accès depuis iPad

`admin.html` **est déployé** sur osm-music.fr. Le problème n'est pas le déploiement.

La cause probable : le **lien "Admin" dans index.html est conditionnel** —
il n'apparaît que si un cookie/session Supabase actif est détecté, ou il est
masqué par une media query mobile. Voir diagnostic séparé (message suivant).

---

## Ce qu'il faut faire pour accéder depuis iPad

1. Ouvrir Safari sur iPad
2. Aller directement sur : **https://osm-music.fr/admin.html**
3. Se connecter avec ton email + mot de passe Supabase admin
4. Mettre la page en **signet Safari** (Partager → Ajouter aux favoris)

Le lien "Admin" qui disparaît sur iPad est un problème séparé d'affichage
dans index.html — il ne bloque pas l'accès direct à admin.html.

---

## Pourquoi admin.html est absent de la branche feature

La branche `claude/osm-website-setup-Sh13W` a divergé de `main` avant que
`admin.html` soit mergé. Il faudra le rapatrier lors du merge final.

```bash
# Pour récupérer admin.html sur la branche feature :
git checkout main -- admin.html
```

---

## Recommandations sécurité (hors périmètre immédiat)

| Risque | Niveau | Fichier |
|---|---|---|
| `login.html` mot de passe `osm2026` en clair dans le JS | ⚠️ Moyen | login.html |
| `login-monteurs.html` credentials hardcodés | ⚠️ Moyen | login-monteurs.html |
| `admin.html` protégé par Supabase | ✅ OK | admin.html |
