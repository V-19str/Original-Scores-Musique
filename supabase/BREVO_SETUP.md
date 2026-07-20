# Emails automatiques (Brevo) — configuration

Objectif : recevoir un email sur **vladimirstreiff@gmail.com** à chaque
**nouvelle demande d'accès** et à chaque **téléchargement**.

La clé API Brevo n'est **jamais** dans le code ni sur le site : elle vit dans un
**secret Supabase**, utilisée uniquement côté serveur par l'Edge Function
`notifier-admin`.

Ordre des opérations : 1 → 5. Compter ~15 minutes.

---

## 1. Créer la clé API Brevo

1. Aller sur https://app.brevo.com → se connecter au compte existant.
2. En haut à droite : menu du compte → **SMTP & API** (ou directement
   https://app.brevo.com/settings/keys/api).
3. Onglet **API Keys** → **Generate a new API key**.
4. Nom : `OSM Supabase`. Cliquer **Generate**.
5. **Copier la clé immédiatement** (elle commence par `xkeysib-…`) — elle ne
   sera plus affichée ensuite. La garder de côté pour l'étape 3.

## 2. Vérifier un expéditeur dans Brevo

Brevo n'envoie qu'avec une adresse d'expéditeur vérifiée.

1. Menu **Senders, Domains & Dedicated IPs** → **Senders**
   (https://app.brevo.com/senders/list).
2. **Add a sender** : nom `OSM — Original Scores Music`, email
   `vladimirstreiff@gmail.com` (ou une autre adresse que tu contrôles).
3. Valider le lien de confirmation reçu par email.
   → C'est cette adresse qui ira dans le secret `SENDER_EMAIL` (étape 3).

## 3. Enregistrer les secrets dans Supabase

Deux méthodes au choix.

**A. Interface web** (le plus simple) :
Dashboard Supabase → projet OSM → **Edge Functions** → **Manage secrets**
(ou **Project Settings → Edge Functions → Secrets**). Ajouter :

| Nom | Valeur |
|-----|--------|
| `BREVO_API_KEY` | la clé `xkeysib-…` de l'étape 1 |
| `SENDER_EMAIL` | l'adresse vérifiée à l'étape 2 |
| `SENDER_NAME` | `OSM — Original Scores Music` (optionnel) |
| `ADMIN_EMAIL` | `vladimirstreiff@gmail.com` (optionnel, c'est le défaut) |
| `OSM_WEBHOOK_SECRET` | une chaîne aléatoire que tu choisis, ex. `osm-hook-9f3a…` |

**B. CLI** :
```bash
supabase secrets set BREVO_API_KEY="xkeysib-…" SENDER_EMAIL="vladimirstreiff@gmail.com" \
  SENDER_NAME="OSM — Original Scores Music" ADMIN_EMAIL="vladimirstreiff@gmail.com" \
  OSM_WEBHOOK_SECRET="osm-hook-9f3a…" --project-ref ubpmzncfhkohoyfonjbb
```

> `OSM_WEBHOOK_SECRET` est facultatif mais recommandé : il empêche que
> quelqu'un déclenche l'envoi d'emails en appelant la fonction à la main.
> Note la valeur, elle sert à l'étape 5.

## 4. Déployer l'Edge Function

Le code est dans `supabase/functions/notifier-admin/index.ts`.

**CLI** :
```bash
supabase functions deploy notifier-admin --project-ref ubpmzncfhkohoyfonjbb
```

**Sans CLI** : Dashboard → Edge Functions → **Create a new function** →
nom `notifier-admin` → coller le contenu de `index.ts` → **Deploy**.

L'URL de la fonction sera :
`https://ubpmzncfhkohoyfonjbb.supabase.co/functions/v1/notifier-admin`

## 5. Créer les deux Database Webhooks

Dashboard Supabase → **Database → Webhooks** → **Enable webhooks** si demandé,
puis **Create a new hook**, deux fois :

**Webhook A — demandes d'accès**
- Name : `notify-access-request`
- Table : `public.access_requests`
- Events : cocher **Insert** uniquement
- Type : **HTTP Request** → **POST**
- URL : `https://ubpmzncfhkohoyfonjbb.supabase.co/functions/v1/notifier-admin`
- HTTP Headers : ajouter
  - `Content-Type` : `application/json`
  - `x-osm-secret` : la valeur de `OSM_WEBHOOK_SECRET` (étape 3, si défini)

**Webhook B — téléchargements**
- Name : `notify-download`
- Table : `public.downloads`
- Events : **Insert** uniquement
- URL et headers : identiques au webhook A.

> Si tu n'as pas défini `OSM_WEBHOOK_SECRET`, n'ajoute pas l'en-tête
> `x-osm-secret` : la fonction accepte alors tous les appels.

---

## Vérifier que ça marche

1. **Demande d'accès** : remplir le formulaire sur https://osm-music.fr/inscription.html
   → un email « Nouvelle demande d'accès » doit arriver, et la demande apparaît
   dans `admin.html` → section « Demandes d'accès ».
2. **Téléchargement** : en tant que client connecté, télécharger un titre
   → un email « Téléchargement — … » doit arriver.
3. En cas de souci : Dashboard → Edge Functions → `notifier-admin` → **Logs**.
   Les erreurs Brevo (clé, expéditeur non vérifié) y sont visibles.

## Notes

- Offre gratuite Brevo : ~300 emails/jour. Suffisant ; au-delà, passer à un plan
  payant ou regrouper les notifications de téléchargement.
- Le formulaire d'inscription continue aussi d'envoyer via **Formspree** (canal
  de secours). Pour ne garder que Brevo, désactiver le formulaire Formspree plus
  tard — la demande sera toujours enregistrée en base et notifiée par Brevo.
