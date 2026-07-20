// Supabase Edge Function : notifier-admin
// Envoie un email à l'administrateur OSM via Brevo à chaque :
//   - nouvelle demande d'accès (INSERT sur public.access_requests)
//   - nouveau téléchargement   (INSERT sur public.downloads)
//
// Déclenchée par un Database Webhook Supabase (un par table). La clé Brevo n'est
// JAMAIS dans le code ni côté client : elle est lue depuis un secret Supabase.
//
// Déploiement :
//   supabase functions deploy notifier-admin --project-ref ubpmzncfhkohoyfonjbb
//
// Secrets à définir (voir supabase/BREVO_SETUP.md) :
//   BREVO_API_KEY       (obligatoire) — clé API v3 Brevo
//   SENDER_EMAIL        (obligatoire) — expéditeur vérifié dans Brevo
//   SENDER_NAME         (optionnel)   — nom d'expéditeur, défaut « OSM »
//   ADMIN_EMAIL         (optionnel)   — destinataire, défaut vladimirstreiff@gmail.com
//   OSM_WEBHOOK_SECRET  (optionnel)   — si défini, le webhook doit envoyer
//                                       l'en-tête x-osm-secret avec cette valeur
// Variables fournies automatiquement par Supabase :
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ADMIN_EMAIL = Deno.env.get("ADMIN_EMAIL") ?? "vladimirstreiff@gmail.com";
const SENDER_EMAIL = Deno.env.get("SENDER_EMAIL") ?? "";
const SENDER_NAME = Deno.env.get("SENDER_NAME") ?? "OSM — Original Scores Music";
const BREVO_API_KEY = Deno.env.get("BREVO_API_KEY") ?? "";
const WEBHOOK_SECRET = Deno.env.get("OSM_WEBHOOK_SECRET") ?? "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-osm-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

function esc(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function sendBrevo(subject: string, html: string) {
  if (!BREVO_API_KEY || !SENDER_EMAIL) {
    throw new Error("BREVO_API_KEY ou SENDER_EMAIL manquant (secrets Supabase).");
  }
  const res = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: {
      "api-key": BREVO_API_KEY,
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({
      sender: { name: SENDER_NAME, email: SENDER_EMAIL },
      to: [{ email: ADMIN_EMAIL }],
      subject,
      htmlContent: html,
    }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Brevo ${res.status} : ${txt}`);
  }
}

// Demande d'accès → email récapitulatif.
function accessRequestEmail(r: Record<string, unknown>) {
  const name = [r.prenom, r.nom].filter(Boolean).join(" ") || String(r.email ?? "");
  const rows: [string, unknown][] = [
    ["Nom", name], ["Email", r.email], ["Téléphone", r.telephone],
    ["Société", r.societe], ["Métier", r.metier], ["Projet", r.projet],
    ["Message", r.message],
  ];
  const body = rows
    .filter(([, v]) => v)
    .map(([k, v]) => `<tr><td style="padding:4px 12px 4px 0;color:#888">${k}</td><td style="padding:4px 0"><strong>${esc(v)}</strong></td></tr>`)
    .join("");
  return {
    subject: `Nouvelle demande d'accès — ${name}`,
    html: `<div style="font-family:Arial,sans-serif;font-size:14px;color:#111">
      <h2 style="color:#E50914;margin:0 0 12px">Nouvelle demande d'accès OSM</h2>
      <table style="border-collapse:collapse">${body}</table>
      <p style="margin-top:16px"><a href="https://osm-music.fr/admin.html" style="color:#E50914">Ouvrir le panneau admin →</a></p>
    </div>`,
  };
}

// Téléchargement → email court. On complète avec le profil du client si dispo.
async function downloadEmail(r: Record<string, unknown>) {
  let who = "";
  const admin = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { autoRefreshToken: false, persistSession: false } },
  );
  if (r.user_id) {
    const { data } = await admin.from("profiles")
      .select("email, prenom, nom").eq("id", r.user_id).single();
    if (data) who = [data.prenom, data.nom].filter(Boolean).join(" ") || data.email || "";
  }
  const title = String(r.track_title ?? r.track_id ?? "un titre");
  const playlist = r.track_playlist ? ` (${esc(r.track_playlist)})` : "";
  return {
    subject: `Téléchargement — ${title}`,
    html: `<div style="font-family:Arial,sans-serif;font-size:14px;color:#111">
      <h2 style="color:#E50914;margin:0 0 12px">Nouveau téléchargement</h2>
      <p><strong>${esc(title)}</strong>${playlist}</p>
      ${who ? `<p>par <strong>${esc(who)}</strong></p>` : ""}
      <p style="margin-top:16px"><a href="https://osm-music.fr/admin.html" style="color:#E50914">Ouvrir le panneau admin →</a></p>
    </div>`,
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Méthode non autorisée." }, 405);

  // Contrôle optionnel du secret partagé avec le webhook.
  if (WEBHOOK_SECRET && req.headers.get("x-osm-secret") !== WEBHOOK_SECRET) {
    return json({ error: "Secret invalide." }, 401);
  }

  let payload: { type?: string; table?: string; record?: Record<string, unknown> };
  try {
    payload = await req.json();
  } catch {
    return json({ error: "Corps de requête invalide." }, 400);
  }

  const record = payload.record ?? {};
  const table = payload.table ?? "";

  try {
    let mail: { subject: string; html: string };
    if (table === "access_requests") {
      mail = accessRequestEmail(record);
    } else if (table === "downloads") {
      mail = await downloadEmail(record);
    } else {
      return json({ ok: true, skipped: `table non gérée : ${table}` });
    }
    await sendBrevo(mail.subject, mail.html);
    return json({ ok: true });
  } catch (e) {
    console.error("notifier-admin:", e instanceof Error ? e.message : e);
    return json({ error: e instanceof Error ? e.message : "Échec de l'envoi." }, 500);
  }
});
