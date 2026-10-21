# Tuteur d'orientation « Cap » — mise en ligne

Cette Edge Function fait le lien sécurisé entre la page `orientation.html` et l'IA
Claude (Anthropic). **La clé API reste côté serveur** — elle n'apparaît jamais dans
le navigateur.

```
Navigateur (orientation.html)
        │  POST { profile, messages }
        ▼
Edge Function Supabase : tuteur-orientation   ← garde ANTHROPIC_API_KEY secrète
        │  appel API Claude (streaming)
        ▼
   Anthropic (modèle claude-opus-4-8)
```

## 1. Obtenir une clé API Anthropic

1. Créer un compte sur https://console.anthropic.com
2. Ajouter un moyen de paiement / crédits (l'IA est facturée à l'usage).
3. Générer une clé API (commence par `sk-ant-...`).

## 2. Enregistrer la clé comme secret Supabase

```bash
supabase secrets set ANTHROPIC_API_KEY=sk-ant-VOTRE_CLE --project-ref ubpmzncfhkohoyfonjbb
```

## 3. Déployer la fonction

La page est utilisée par des élèves **non connectés** : on désactive donc la
vérification du JWT utilisateur (`--no-verify-jwt`). L'accès reste protégé par la
clé publiable Supabase déjà utilisée par le site.

```bash
supabase functions deploy tuteur-orientation --no-verify-jwt --project-ref ubpmzncfhkohoyfonjbb
```

## 4. Tester

Ouvrir `https://osm-music.fr/orientation.html` (ou la page en local), remplir le
questionnaire, puis discuter avec Cap. Les réponses doivent s'afficher au fil de
l'eau (streaming).

Test rapide en ligne de commande :

```bash
curl -N -X POST \
  https://ubpmzncfhkohoyfonjbb.supabase.co/functions/v1/tuteur-orientation \
  -H "Authorization: Bearer sb_publishable_8rWkPwFktGZLsk79WCq7PQ_3Gb1xykh" \
  -H "apikey: sb_publishable_8rWkPwFktGZLsk79WCq7PQ_3Gb1xykh" \
  -H "Content-Type: application/json" \
  -d '{"profile":{"prenom":"Léa","niveau":"Terminale","filiere":"Générale","perdu":true},
       "messages":[{"role":"user","content":"Bonjour, je suis un peu perdue, peux-tu m aider ?"}]}'
```

## Réglages utiles

- **Changer de modèle / réduire le coût** : dans `index.ts`, la constante `MODEL`.
  `claude-opus-4-8` = qualité maximale. `claude-sonnet-5` = nettement moins cher et
  très rapide, qualité proche pour ce type de conversation.
- **Adapter le ton / la mission de Cap** : fonction `buildSystemPrompt` dans `index.ts`.
- **Garde-fous anti-abus** : constantes `MAX_MESSAGES` et `MAX_CONTENT_CHARS`.

## Notes

- La fonction est **publique** (appelable avec la clé publiable). Pour un site à
  fort trafic, pensez à ajouter une limite de débit (rate limiting) — par ex. via
  un compteur en base ou un service devant la fonction — afin de maîtriser la
  facture Anthropic.
- Le system prompt interdit à Cap d'inventer des dates ou des statistiques
  Parcoursup et le renvoie vers les sources officielles (parcoursup.fr, onisep.fr).
