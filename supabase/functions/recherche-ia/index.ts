// Supabase Edge Function : recherche-ia
// Reçoit une requête en langage naturel, appelle Claude pour extraire
// les tags pertinents, renvoie {tags, intention} au client qui filtre
// allTracks côté navigateur.
//
// Déploiement :
//   supabase functions deploy recherche-ia --project-ref ubpmzncfhkohoyfonjbb
//
// Secrets requis :
//   ANTHROPIC_API_KEY

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const ANTHROPIC_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    const { query } = await req.json();
    if (!query || String(query).trim().length < 3) {
      return new Response(
        JSON.stringify({ error: "Requête trop courte" }),
        { status: 400, headers: { ...cors, "Content-Type": "application/json" } }
      );
    }

    const prompt = `Tu es un assistant pour OSM, bibliothèque de musique originale française pour le cinéma, la télévision et la publicité.
Un monteur vidéo cherche : "${String(query).trim()}"

Retourne UNIQUEMENT un objet JSON valide (sans markdown) avec :
- "tags": tableau de 6 à 12 tags en français parmi ces valeurs possibles :
  ambiance: sombre, tendu, mélancolique, joyeux, épique, intense, dramatique, lumineux, calme, positif, énergique, festif, puissant, doux, introspectif
  synonymes: suspense, angoisse, thriller, héroïque, nostalgique, triste, nerveux, frénétique, paisible, serein, grandiose, triomphal
  tempo: lent, modéré, rapide, très rapide
  énergie: haute énergie, énergie moyenne, faible énergie
  genre: orchestral, électronique, acoustique, jazz, ambient, hybride
  instruments: piano, cordes, cuivres, guitare, percussions, synthétiseur
  usage: cinéma, publicité, documentaire
- "intention": une phrase courte (max 12 mots) expliquant le choix, ex: "Titres intenses et dramatiques pour une scène d'action"

Exemple de sortie :
{"tags":["tendu","intense","rapide","orchestral","suspense","cinéma","haute énergie"],"intention":"Musique tendue et rythmée pour une scène de poursuite"}`;

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5",
        max_tokens: 300,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`Claude ${resp.status}: ${err.slice(0, 120)}`);
    }

    const claude = await resp.json();
    const text = claude.content?.[0]?.text?.trim() ?? "{}";
    const parsed = JSON.parse(text);

    return new Response(
      JSON.stringify({
        tags: Array.isArray(parsed.tags) ? parsed.tags : [],
        intention: typeof parsed.intention === "string" ? parsed.intention : "",
      }),
      { headers: { ...cors, "Content-Type": "application/json" } }
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ error: String((e as Error).message) }),
      { status: 500, headers: { ...cors, "Content-Type": "application/json" } }
    );
  }
});
