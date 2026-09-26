// Supabase Edge Function : notifier-admin
// Envoie un email à l'administrateur OSM via Brevo pour :
//   - nouvelle inscription (appelé directement depuis inscription.html)
//   - nouvelle connexion   (appelé directement depuis login-monteurs.html)
//   - nouveau téléchargement (Database Webhook Supabase sur public.downloads)
//   - demande d'accès (Database Webhook sur public.access_requests)
//
// Appels directs : header x-admin-secret: OSM_ADMIN_2026
// Webhook Supabase : header x-osm-secret: <OSM_WEBHOOK_SECRET>
//
// Déploiement :
//   supabase functions deploy notifier-admin --project-ref ubpmzncfhkohoyfonjbb
//
// Secrets Supabase requis :
//   BREVO_API_KEY, SENDER_EMAIL
//   SENDER_NAME (optionnel), ADMIN_EMAIL (optionnel)
//   OSM_WEBHOOK_SECRET (optionnel, pour les webhooks Supabase)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const OSM_ADMIN_SECRET = "OSM_ADMIN_2026";
const ADMIN_EMAIL      = Deno.env.get("ADMIN_EMAIL")  ?? "vladimirstreiff@gmail.com";
const SENDER_EMAIL     = Deno.env.get("SENDER_EMAIL") ?? "";
const SENDER_NAME      = Deno.env.get("SENDER_NAME")  ?? "OSM — Original Scores Music";
const BREVO_API_KEY    = Deno.env.get("BREVO_API_KEY") ?? "";
const WEBHOOK_SECRET   = Deno.env.get("OSM_WEBHOOK_SECRET") ?? "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, apikey, content-type, x-osm-secret, x-admin-secret",
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

function card(content: string) {
  return `<div style="font-family:Arial,sans-serif;max-width:500px;color:#111">
    <div style="background:#111;padding:14px 20px;border-radius:6px 6px 0 0;display:flex;align-items:center;gap:10px">
      <div style="background:#E50914;color:#fff;font-size:11px;font-weight:700;letter-spacing:2px;padding:4px 8px;border-radius:3px">OSM</div>
    </div>
    <div style="background:#fff;border:1px solid #eee;border-top:none;padding:22px;border-radius:0 0 6px 6px">
      ${content}
      <p style="margin-top:18px">
        <a href="https://osm-music.fr/admin.html" style="background:#E50914;color:#fff;padding:9px 20px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:700">Ouvrir le panneau admin →</a>
      </p>
    </div>
  </div>`;
}

// ── Nouvelle inscription ────────────────────────────────────────────────────
function signupEmail(d: Record<string, unknown>) {
  const name = [d.prenom, d.nom].filter(Boolean).join(" ") || String(d.email ?? "—");
  const rows: [string, unknown][] = [
    ["Nom", name], ["Email", d.email], ["Société", d.societe],
    ["Téléphone", d.telephone], ["Métier", d.metier], ["Projet", d.projet], ["Message", d.message],
  ];
  const table = rows.filter(([, v]) => v).map(([k, v]) =>
    `<tr><td style="padding:4px 12px 4px 0;color:#888;font-size:12px">${k}</td><td style="padding:4px 0;font-size:13px"><strong>${esc(v)}</strong></td></tr>`
  ).join("");
  return {
    subject: `✅ Nouvelle inscription — ${name}`,
    html: card(`
      <h2 style="margin:0 0 14px;font-size:16px;color:#E50914">Nouvelle inscription OSM</h2>
      <table style="border-collapse:collapse">${table}</table>
    `),
  };
}

// ── Nouvelle connexion ──────────────────────────────────────────────────────
function loginEmail(d: Record<string, unknown>) {
  const name = [d.prenom, d.nom].filter(Boolean).join(" ") || String(d.email ?? "—");
  const now = new Date().toLocaleString("fr-FR", {
    timeZone: "Europe/Paris", day: "2-digit", month: "2-digit",
    year: "numeric", hour: "2-digit", minute: "2-digit",
  });
  return {
    subject: `🔑 Connexion — ${name}`,
    html: card(`
      <h2 style="margin:0 0 14px;font-size:16px;color:#333">Connexion client</h2>
      <p style="font-size:14px"><strong>${esc(name)}</strong></p>
      <p style="font-size:12px;color:#888">${esc(String(d.email ?? ""))} · ${now}</p>
    `),
  };
}

// ── Demande d'accès (ancien webhook) ───────────────────────────────────────
function accessRequestEmail(r: Record<string, unknown>) {
  const name = [r.prenom, r.nom].filter(Boolean).join(" ") || String(r.email ?? "");
  const rows: [string, unknown][] = [
    ["Nom", name], ["Email", r.email], ["Téléphone", r.telephone],
    ["Société", r.societe], ["Métier", r.metier], ["Projet", r.projet], ["Message", r.message],
  ];
  const table = rows.filter(([, v]) => v).map(([k, v]) =>
    `<tr><td style="padding:4px 12px 4px 0;color:#888">${k}</td><td style="padding:4px 0"><strong>${esc(v)}</strong></td></tr>`
  ).join("");
  return {
    subject: `Nouvelle demande d'accès — ${name}`,
    html: card(`
      <h2 style="margin:0 0 12px;font-size:16px;color:#E50914">Demande d'accès OSM</h2>
      <table style="border-collapse:collapse">${table}</table>
    `),
  };
}

// ── Téléchargement (webhook) ────────────────────────────────────────────────
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
  const playlist = r.track_playlist ? ` <span style="color:#888">(${esc(r.track_playlist)})</span>` : "";
  return {
    subject: `⬇ Téléchargement — ${esc(title)}`,
    html: card(`
      <h2 style="margin:0 0 14px;font-size:16px;color:#333">Nouveau téléchargement</h2>
      <p style="font-size:14px"><strong>${esc(title)}</strong>${playlist}</p>
      ${who ? `<p style="font-size:12px;color:#888">par <strong>${esc(who)}</strong></p>` : ""}
    `),
  };
}

// ── Serveur ─────────────────────────────────────────────────────────────────
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Méthode non autorisée." }, 405);

  // Auth : appel direct (x-admin-secret) OU webhook (x-osm-secret)
  const adminSecret   = req.headers.get("x-admin-secret") ?? "";
  const webhookSecret = req.headers.get("x-osm-secret")   ?? "";

  const isDirectCall = adminSecret === OSM_ADMIN_SECRET;
  const isWebhook    = WEBHOOK_SECRET ? webhookSecret === WEBHOOK_SECRET : true;

  if (!isDirectCall && !isWebhook) {
    return json({ error: "Accès refusé." }, 401);
  }

  let payload: Record<string, unknown>;
  try {
    payload = await req.json();
  } catch {
    return json({ error: "Corps de requête invalide." }, 400);
  }

  const event = String(payload.event ?? "");
  const table = String(payload.table ?? "");
  const record = (payload.record as Record<string, unknown>) ?? payload;

  try {
    let mail: { subject: string; html: string };

    if (event === "signup") {
      mail = signupEmail(record);
    } else if (event === "login") {
      mail = loginEmail(record);
    } else if (table === "access_requests") {
      mail = accessRequestEmail(record);
    } else if (table === "downloads") {
      mail = await downloadEmail(record);
    } else {
      return json({ ok: true, skipped: `événement non géré : ${event || table}` });
    }

    await sendBrevo(mail.subject, mail.html);
    return json({ ok: true });
  } catch (e) {
    console.error("notifier-admin:", e instanceof Error ? e.message : e);
    return json({ error: e instanceof Error ? e.message : "Échec de l'envoi." }, 500);
  }
});
