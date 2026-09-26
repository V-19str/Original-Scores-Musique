// Supabase Edge Function : daily-recap
// Envoie chaque matin à l'admin un récapitulatif de l'activité des 24h :
//   - nouvelles inscriptions
//   - connexions
//   - écoutes
//   - téléchargements
//
// Appelée par un GitHub Actions cron à 6h UTC (= 8h Paris heure d'été).
// Sécurisée par x-admin-secret.
//
// Déploiement :
//   supabase functions deploy daily-recap --project-ref ubpmzncfhkohoyfonjbb
//
// Secrets Supabase requis (mêmes que notifier-admin) :
//   BREVO_API_KEY, SENDER_EMAIL
//   SENDER_NAME (optionnel), ADMIN_EMAIL (optionnel)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ADMIN_SECRET  = "OSM_ADMIN_2026";
const ADMIN_EMAIL   = Deno.env.get("ADMIN_EMAIL")  ?? "vladimirstreiff@gmail.com";
const SENDER_EMAIL  = Deno.env.get("SENDER_EMAIL") ?? "";
const SENDER_NAME   = Deno.env.get("SENDER_NAME")  ?? "OSM — Original Scores Music";
const BREVO_API_KEY = Deno.env.get("BREVO_API_KEY") ?? "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-admin-secret",
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

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    timeZone: "Europe/Paris",
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

async function sendBrevo(subject: string, html: string) {
  if (!BREVO_API_KEY || !SENDER_EMAIL) {
    throw new Error("BREVO_API_KEY ou SENDER_EMAIL manquant.");
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

function buildEmail(
  date: string,
  signups: Array<{ email: string; prenom: string | null; nom: string | null; created_at: string }>,
  connections: Array<{ email: string; prenom: string | null; nom: string | null; last_sign_in: string }>,
  plays: Array<{ track_title: string | null; track_playlist: string | null; email: string | null; played_at: string }>,
  downloads: Array<{ track_title: string | null; track_playlist: string | null; email: string | null; downloaded_at: string }>,
) {
  const total = signups.length + connections.length + plays.length + downloads.length;
  const noActivity = total === 0;

  const blockStyle = "background:#f8f8f8;border-left:3px solid #E50914;padding:14px 18px;margin-bottom:18px;border-radius:0 6px 6px 0";
  const h3Style = "margin:0 0 10px;font-size:14px;color:#E50914;letter-spacing:1px;text-transform:uppercase";
  const rowStyle = "padding:5px 0;border-bottom:1px solid #eee;font-size:13px;color:#333;display:flex;justify-content:space-between;gap:16px";
  const mutedStyle = "color:#888;font-size:12px";

  function section(icon: string, title: string, count: number, rows: string) {
    if (count === 0) return `
      <div style="${blockStyle}">
        <h3 style="${h3Style}">${icon} ${esc(title)} <span style="${mutedStyle}">(0)</span></h3>
        <p style="margin:0;font-size:12px;color:#aaa;font-style:italic">Aucune activité</p>
      </div>`;
    return `
      <div style="${blockStyle}">
        <h3 style="${h3Style}">${icon} ${esc(title)} <span style="${mutedStyle}">(${count})</span></h3>
        ${rows}
      </div>`;
  }

  const signupRows = signups.map(s => {
    const name = [s.prenom, s.nom].filter(Boolean).join(" ") || s.email;
    return `<div style="${rowStyle}"><span><strong>${esc(name)}</strong> — ${esc(s.email)}</span><span style="${mutedStyle}">${fmtDateTime(s.created_at)}</span></div>`;
  }).join("");

  const connRows = connections.map(c => {
    const name = [c.prenom, c.nom].filter(Boolean).join(" ") || c.email;
    return `<div style="${rowStyle}"><span><strong>${esc(name)}</strong> — ${esc(c.email)}</span><span style="${mutedStyle}">${fmtDateTime(c.last_sign_in)}</span></div>`;
  }).join("");

  const playRows = plays.map(p =>
    `<div style="${rowStyle}"><span><strong>${esc(p.track_title || "Sans titre")}</strong>${p.track_playlist ? ` <span style="${mutedStyle}">(${esc(p.track_playlist)})</span>` : ""}</span><span style="${mutedStyle}">${esc(p.email || "—")} · ${fmtDateTime(p.played_at)}</span></div>`
  ).join("");

  const dlRows = downloads.map(d =>
    `<div style="${rowStyle}"><span><strong>${esc(d.track_title || "Sans titre")}</strong>${d.track_playlist ? ` <span style="${mutedStyle}">(${esc(d.track_playlist)})</span>` : ""}</span><span style="${mutedStyle}">${esc(d.email || "—")} · ${fmtDateTime(d.downloaded_at)}</span></div>`
  ).join("");

  return `
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#111">
  <div style="background:#111;padding:18px 24px;border-radius:8px 8px 0 0;display:flex;align-items:center;gap:12px">
    <div style="background:#E50914;color:#fff;font-size:11px;font-weight:700;letter-spacing:2px;padding:5px 8px;border-radius:3px">OSM</div>
    <span style="color:#fff;font-size:15px;font-weight:700;letter-spacing:1px">Récap quotidien</span>
    <span style="margin-left:auto;color:#888;font-size:12px">${esc(date)}</span>
  </div>

  <div style="background:#fff;padding:24px;border:1px solid #eee;border-top:none;border-radius:0 0 8px 8px">

    ${noActivity ? `<p style="text-align:center;color:#aaa;padding:40px 0;font-size:14px">Aucune activité hier — tout est calme 🎵</p>` : ""}

    ${section("✉️", "Nouvelles inscriptions", signups.length, signupRows)}
    ${section("🔑", "Connexions", connections.length, connRows)}
    ${section("▶", "Écoutes", plays.length, playRows)}
    ${section("⬇", "Téléchargements", downloads.length, dlRows)}

    <p style="margin-top:20px;text-align:center">
      <a href="https://osm-music.fr/admin.html" style="background:#E50914;color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none;font-size:13px;font-weight:700">Ouvrir le panneau admin →</a>
    </p>
  </div>
</div>`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Méthode non autorisée." }, 405);

  const secret = req.headers.get("x-admin-secret") ?? "";
  if (secret !== ADMIN_SECRET) return json({ error: "Accès refusé." }, 403);

  const SURL = Deno.env.get("SUPABASE_URL")!;
  const SKEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const admin = createClient(SURL, SKEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  // Nouvelles inscriptions (profiles créés dans les 24h)
  const { data: signups } = await admin
    .from("profiles")
    .select("email, prenom, nom, created_at")
    .gte("created_at", since)
    .order("created_at", { ascending: false });

  // Connexions récentes : dernière connexion dans les 24h
  const { data: connProfiles } = await admin
    .from("profiles")
    .select("email, prenom, nom, last_sign_in")
    .gte("last_sign_in", since)
    .order("last_sign_in", { ascending: false });

  // Écoutes des 24h (si la table plays existe)
  const { data: plays } = await admin
    .from("plays")
    .select("track_title, track_playlist, played_at, user_id")
    .gte("played_at", since)
    .order("played_at", { ascending: false })
    .limit(100);

  // Téléchargements des 24h
  const { data: downloads } = await admin
    .from("downloads")
    .select("track_title, track_playlist, downloaded_at, user_id")
    .gte("downloaded_at", since)
    .order("downloaded_at", { ascending: false });

  // Résoudre les emails pour plays et downloads
  const userIds = [
    ...new Set([
      ...(plays ?? []).map(p => p.user_id).filter(Boolean),
      ...(downloads ?? []).map(d => d.user_id).filter(Boolean),
    ])
  ];
  const emailMap: Record<string, string> = {};
  if (userIds.length) {
    const { data: profs } = await admin
      .from("profiles")
      .select("id, email")
      .in("id", userIds);
    (profs ?? []).forEach(p => { emailMap[p.id] = p.email; });
  }

  const playsWithEmail = (plays ?? []).map(p => ({
    ...p,
    email: p.user_id ? (emailMap[p.user_id] ?? null) : null,
  }));
  const dlsWithEmail = (downloads ?? []).map(d => ({
    ...d,
    email: d.user_id ? (emailMap[d.user_id] ?? null) : null,
  }));

  const dateLabel = new Date().toLocaleDateString("fr-FR", {
    timeZone: "Europe/Paris",
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  const html = buildEmail(
    dateLabel,
    signups ?? [],
    connProfiles ?? [],
    playsWithEmail,
    dlsWithEmail,
  );

  const totalActivity = (signups?.length ?? 0) + (connProfiles?.length ?? 0)
    + (plays?.length ?? 0) + (downloads?.length ?? 0);

  const subject = totalActivity > 0
    ? `OSM · Récap du ${dateLabel} — ${totalActivity} événement${totalActivity > 1 ? "s" : ""}`
    : `OSM · Récap du ${dateLabel} — calme plat`;

  try {
    await sendBrevo(subject, html);
    return json({ ok: true, sent: true, events: totalActivity });
  } catch (e) {
    console.error("daily-recap:", e instanceof Error ? e.message : e);
    return json({ error: e instanceof Error ? e.message : "Échec envoi." }, 500);
  }
});
