// Supabase Edge Function : tuteur-orientation
// Tuteur d'orientation IA bienveillant et rassurant (Parcoursup / post-bac).
// Proxy sécurisé vers l'API Claude — la clé ANTHROPIC_API_KEY reste côté serveur,
// jamais exposée au navigateur. Répond en streaming (SSE) pour un chat fluide.
//
// Déploiement (voir README.md dans ce dossier) :
//   supabase secrets set ANTHROPIC_API_KEY=sk-ant-... --project-ref ubpmzncfhkohoyfonjbb
//   supabase functions deploy tuteur-orientation --no-verify-jwt --project-ref ubpmzncfhkohoyfonjbb
//
// Contrat d'API (POST JSON) :
//   { profile: { prenom, niveau, filiere, specialites, matieres, interets,
//                projet, perdu, mobilite, autres },
//     messages: [ { role: "user" | "assistant", content: "..." }, ... ] }
// Réponse : text/event-stream, événements « data: {"text":"..."} » puis « data: {"done":true} ».

// Modèle Claude utilisé. Pour réduire le coût sur un chatbot à fort trafic,
// vous pouvez remplacer par "claude-sonnet-5" (moins cher, très rapide, qualité proche).
const MODEL = "claude-opus-4-8";
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";

// Garde-fous anti-abus (la fonction est publique).
const MAX_MESSAGES = 40;
const MAX_CONTENT_CHARS = 6000;

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

function clip(s: unknown, max: number): string {
  return String(s ?? "").slice(0, max).trim();
}

interface Profile {
  prenom?: string;
  niveau?: string;
  filiere?: string;
  specialites?: string;
  matieres?: string;
  interets?: string;
  projet?: string;
  perdu?: boolean;
  mobilite?: string;
  autres?: string;
}

// Construit la partie « profil de l'élève » du system prompt.
function formatProfile(p: Profile): string {
  const lines: string[] = [];
  const add = (label: string, value?: string) => {
    const v = clip(value, 600);
    if (v) lines.push(`- ${label} : ${v}`);
  };
  add("Prénom", p.prenom);
  add("Niveau / classe", p.niveau);
  add("Filière", p.filiere);
  add("Spécialités / options", p.specialites);
  add("Matières préférées et points forts", p.matieres);
  add("Centres d'intérêt", p.interets);
  add("Projet / métier envisagé", p.projet);
  add("Mobilité géographique", p.mobilite);
  add("Autres informations", p.autres);
  if (p.perdu) {
    lines.push(
      "- État d'esprit : l'élève se sent PERDU·E ou stressé·e. Sois particulièrement rassurant·e, chaleureux·se et concret·ète.",
    );
  }
  if (lines.length === 0) return "Aucune information de profil n'a encore été fournie.";
  return lines.join("\n");
}

function buildSystemPrompt(p: Profile): string {
  return `Tu es « Cap », un tuteur d'orientation scolaire francophone, bienveillant, chaleureux et profondément rassurant. Tu accompagnes des lycéen·nes et étudiant·es avant et pendant Parcoursup (ainsi que pour l'orientation post-bac en général : réorientation, études supérieures).

## Ta mission
- Analyser le profil de chaque élève avec empathie et sans jamais juger.
- L'aider à y voir clair dans son parcours, surtout s'il/elle se sent perdu·e.
- Proposer des pistes de formations concrètes et adaptées (licences, BUT, BTS, classes prépa, écoles, DN MADE, formations en apprentissage, etc.).
- Proposer des TYPES d'établissements qui correspondent à ses envies (universités, IUT, lycées avec BTS, écoles spécialisées, publiques et privées) — sans inventer de noms précis ni de statistiques d'admission que tu n'es pas sûr·e de connaître.
- Ouvrir grand le champ des possibles en présentant de NOMBREUX débouchés et métiers pour chaque piste, y compris des voies auxquelles l'élève n'aurait pas pensé.
- Rassurer, encourager, dédramatiser dès que l'élève exprime du stress, de l'angoisse ou un sentiment d'échec.

## Ton et style
- Tutoie l'élève, avec un ton doux, positif et encourageant. Utilise son prénom quand tu le connais.
- Sois clair et structuré : phrases courtes, listes à puces, quelques emojis discrets (🌱, 💡, 🎯, 🤝) pour la chaleur, sans excès.
- Célèbre ses points forts avant de proposer des pistes.
- N'accable jamais l'élève de tout d'un coup : donne 3 à 5 pistes prioritaires, puis propose d'approfondir celle qui l'attire.
- Termine souvent par une question ouverte pour l'inviter à continuer le dialogue.

## Rigueur et honnêteté
- Ne t'invente JAMAIS de dates de calendrier Parcoursup, de taux d'accès, de « attendus » précis ou de chiffres d'insertion. Si l'élève a besoin de ces informations, redirige-le vers les sources officielles : parcoursup.fr, l'Onisep (onisep.fr), Mon Master, les journées portes ouvertes et les salons d'orientation.
- Rappelle avec bienveillance que rien n'est jamais définitif : réorientations, passerelles et années de césure existent.
- Reste STRICTEMENT sur le thème de l'orientation, des études et des métiers. Si on te pose une question hors sujet, ramène gentiment vers l'orientation.
- En cas de détresse réelle (mots évoquant un mal-être profond), rassure avec beaucoup de douceur et invite l'élève à en parler à un adulte de confiance, au CPE, à un·e psy-EN (psychologue de l'Éducation nationale), ou à contacter le 3114 (numéro national de prévention du suicide, gratuit, 24h/24).

## Profil de l'élève (fourni par le questionnaire)
${formatProfile(p)}

Réponds toujours en français. Adapte-toi à ce profil dès ton premier message : commence par une phrase rassurante et personnalisée, mets en valeur ses points forts, puis propose des pistes.`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return json({ error: "Méthode non autorisée." }, 405);
  }

  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) {
    return json(
      { error: "Configuration manquante : ANTHROPIC_API_KEY n'est pas défini." },
      500,
    );
  }

  // 1. Lire et valider le corps de la requête.
  let body: { profile?: Profile; messages?: Array<{ role?: string; content?: string }> };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Corps de requête invalide." }, 400);
  }

  const profile = (body.profile ?? {}) as Profile;
  const rawMessages = Array.isArray(body.messages) ? body.messages : [];
  if (rawMessages.length === 0) {
    return json({ error: "Aucun message fourni." }, 400);
  }

  // Nettoyage : ne garder que les derniers messages, rôles valides, contenu borné.
  const messages = rawMessages
    .slice(-MAX_MESSAGES)
    .map((m) => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: clip(m.content, MAX_CONTENT_CHARS),
    }))
    .filter((m) => m.content.length > 0);

  if (messages.length === 0 || messages[0].role !== "user") {
    return json({ error: "Le premier message doit provenir de l'élève." }, 400);
  }

  const systemPrompt = buildSystemPrompt(profile);

  // 2. Appeler l'API Claude en streaming.
  let upstream: Response;
  try {
    upstream = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 4096,
        system: systemPrompt,
        messages,
        stream: true,
      }),
    });
  } catch (e) {
    return json({ error: "Impossible de joindre le service IA.", detail: String(e) }, 502);
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return json(
      { error: "Le service IA a renvoyé une erreur.", status: upstream.status, detail },
      502,
    );
  }

  // 3. Transformer le flux SSE d'Anthropic en un flux simple pour le navigateur.
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const reader = upstream.body.getReader();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: unknown) =>
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      let buffer = "";
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // Découpe les événements SSE (séparés par une ligne vide).
          let sep: number;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const chunk = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            for (const line of chunk.split("\n")) {
              const trimmed = line.trim();
              if (!trimmed.startsWith("data:")) continue;
              const payload = trimmed.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;
              try {
                const evt = JSON.parse(payload);
                if (
                  evt.type === "content_block_delta" &&
                  evt.delta?.type === "text_delta" &&
                  evt.delta.text
                ) {
                  send({ text: evt.delta.text });
                } else if (evt.type === "error") {
                  send({ error: evt.error?.message ?? "Erreur du service IA." });
                }
              } catch {
                // Ligne partielle ou non-JSON : on ignore.
              }
            }
          }
        }
        send({ done: true });
      } catch (e) {
        send({ error: "Interruption du flux : " + String(e) });
      } finally {
        controller.close();
      }
    },
    cancel() {
      reader.cancel().catch(() => {});
    },
  });

  return new Response(stream, {
    headers: {
      ...corsHeaders,
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });
});
