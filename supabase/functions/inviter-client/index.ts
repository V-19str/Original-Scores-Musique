// Supabase Edge Function : inviter-client
// Invite un client par email (Supabase envoie l'email « Vous êtes invité »).
// Seul l'admin OSM (vladimirstreiff@gmail.com) peut appeler cette fonction.
//
// Déploiement :
//   supabase functions deploy inviter-client --project-ref ubpmzncfhkohoyfonjbb
//
// Variables d'environnement fournies automatiquement par Supabase :
//   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ADMIN_EMAIL = "vladimirstreiff@gmail.com";
const REDIRECT_TO = "https://osm-music.fr/finaliser-inscription.html";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return json({ error: "Méthode non autorisée." }, 405);
  }

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
  const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
  const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  // 1. Vérifier que l'appelant est bien l'admin OSM
  const authHeader = req.headers.get("Authorization") ?? "";
  const token = authHeader.replace(/^Bearer\s+/i, "");
  if (!token) {
    return json({ error: "Token d'authentification manquant." }, 401);
  }

  const authClient = createClient(SUPABASE_URL, ANON_KEY);
  const { data: userData, error: userErr } = await authClient.auth.getUser(
    token,
  );
  if (userErr || !userData?.user) {
    return json({ error: "Session invalide ou expirée." }, 401);
  }
  if (userData.user.email?.toLowerCase() !== ADMIN_EMAIL) {
    return json({ error: "Accès refusé : réservé à l'administrateur." }, 403);
  }

  // 2. Lire le corps de la requête
  let body: { email?: string; prenom?: string; nom?: string };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Corps de requête invalide." }, 400);
  }
  const email = (body.email ?? "").trim().toLowerCase();
  const prenom = (body.prenom ?? "").trim();
  const nom = (body.nom ?? "").trim();

  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return json({ error: "Email invalide." }, 400);
  }

  // 3. Envoyer l'invitation avec la clé service_role
  const admin = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data, error } = await admin.auth.admin.inviteUserByEmail(email, {
    data: { prenom, nom },
    redirectTo: REDIRECT_TO,
  });

  if (error) {
    return json({ error: error.message }, 400);
  }

  return json({
    ok: true,
    message: `Invitation envoyée à ${email}.`,
    user_id: data?.user?.id ?? null,
  });
});
