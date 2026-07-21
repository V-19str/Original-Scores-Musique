// Supabase Edge Function : signer-upload
// Signe un upload Cloudinary pour l'ajout d'un morceau depuis admin.html.
//
// Le fichier MP3 ne transite PAS par cette fonction : elle ne renvoie qu'une
// signature à durée de vie courte, et le navigateur poste ensuite le fichier
// directement à Cloudinary. Le secret API Cloudinary reste donc côté serveur,
// et un upload de 30 Mo ne consomme ni la bande passante ni le temps CPU de
// l'Edge Function.
//
// Seul l'admin OSM (vladimirstreiff@gmail.com) peut appeler cette fonction —
// même contrôle que inviter-client : le JWT de session est vérifié auprès de
// Supabase Auth, il ne peut pas être forgé sans le secret du projet.
//
// Déploiement :
//   supabase functions deploy signer-upload --project-ref ubpmzncfhkohoyfonjbb
//
// Secrets à définir (dashboard Supabase → Edge Functions → Secrets) :
//   CLOUDINARY_CLOUD_NAME   (obligatoire) — « dtfm2cwm0 » pour OSM
//   CLOUDINARY_API_KEY      (obligatoire) — clé API Cloudinary
//   CLOUDINARY_API_SECRET   (obligatoire) — secret API Cloudinary
//   CLOUDINARY_FOLDER       (optionnel)   — dossier de destination ; vide par
//                                           défaut, pour que les nouvelles URLs
//                                           aient la même forme que le catalogue
//                                           existant (…/video/upload/v…/ID.mp3)
// Variables fournies automatiquement par Supabase :
//   SUPABASE_URL, SUPABASE_ANON_KEY

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ADMIN_EMAIL = "vladimirstreiff@gmail.com";

const CLOUD_NAME = Deno.env.get("CLOUDINARY_CLOUD_NAME") ?? "";
const API_KEY = Deno.env.get("CLOUDINARY_API_KEY") ?? "";
const API_SECRET = Deno.env.get("CLOUDINARY_API_SECRET") ?? "";
const FOLDER = (Deno.env.get("CLOUDINARY_FOLDER") ?? "").trim();

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

// Cloudinary attend un SHA-1 de « k=v&k=v… » (paramètres triés par clé, hors
// file/api_key/resource_type) suivi du secret API.
async function sign(params: Record<string, string>): Promise<string> {
  const base = Object.keys(params).sort()
    .map((k) => `${k}=${params[k]}`)
    .join("&");
  const bytes = new TextEncoder().encode(base + API_SECRET);
  const digest = await crypto.subtle.digest("SHA-1", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// L'id public sert aussi de track_id dans nouveaux_titres : on le dérive du
// titre pour qu'il reste lisible dans les URLs, avec un suffixe aléatoire pour
// éviter d'écraser un morceau existant qui porterait le même nom.
function makePublicId(title: string): string {
  const slug = title
    .normalize("NFD").replace(/\p{M}/gu, "")   // accents
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60) || "TITRE";
  const suffix = Array.from(crypto.getRandomValues(new Uint8Array(3)))
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${slug}_${suffix}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Méthode non autorisée." }, 405);

  if (!CLOUD_NAME || !API_KEY || !API_SECRET) {
    return json({
      error: "Configuration Cloudinary incomplète (secrets CLOUDINARY_* manquants).",
    }, 500);
  }

  // 1. Vérifier que l'appelant est bien l'admin OSM.
  const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!token) return json({ error: "Token d'authentification manquant." }, 401);

  const authClient = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
  );
  const { data: userData, error: userErr } = await authClient.auth.getUser(token);
  if (userErr || !userData?.user) return json({ error: "Session invalide ou expirée." }, 401);
  if (userData.user.email?.toLowerCase() !== ADMIN_EMAIL) {
    return json({ error: "Accès refusé : réservé à l'administrateur." }, 403);
  }

  // 2. Titre du morceau, qui donne l'id public.
  let body: { title?: string };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Corps de requête invalide." }, 400);
  }
  const title = (body.title ?? "").trim();
  if (!title) return json({ error: "Titre manquant." }, 400);

  // 3. Signature. Les paramètres signés sont exactement ceux que le navigateur
  //    devra renvoyer à Cloudinary : toute divergence invalide la signature,
  //    donc un appelant ne peut pas détourner l'upload ailleurs.
  const timestamp = Math.floor(Date.now() / 1000);
  const publicId = makePublicId(title);
  const toSign: Record<string, string> = {
    public_id: publicId,
    timestamp: String(timestamp),
  };
  if (FOLDER) toSign.folder = FOLDER;

  return json({
    ok: true,
    cloud_name: CLOUD_NAME,
    api_key: API_KEY,
    timestamp,
    public_id: publicId,
    folder: FOLDER || null,
    signature: await sign(toSign),
    // resource_type « video » : Cloudinary range l'audio avec la vidéo, comme
    // le reste du catalogue OSM (…/video/upload/…).
    upload_url: `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/video/upload`,
  });
});
