/* Relais « ambiance » : reçoit 6 images d'une séquence, interroge l'API Anthropic,
   renvoie l'ambiance dans le vocabulaire des playlists OSM.
   Variables d'environnement Vercel : ANTHROPIC_API_KEY (obligatoire), ANTHROPIC_MODEL,
   ALLOWED_ORIGINS, DAILY_LIMIT, KV_REST_API_URL + KV_REST_API_TOKEN (quota partagé, optionnel). */
const PLAYLISTS = require('../playlists.json');

const MODEL = process.env.ANTHROPIC_MODEL || 'claude-sonnet-5-5';
const ORIGINS = (process.env.ALLOWED_ORIGINS || 'https://osm-music.fr,https://www.osm-music.fr').split(',').map(s => s.trim());
const DAILY = +(process.env.DAILY_LIMIT || 30);
const MAX_IMG_B64 = 220 * 1024;   // ~160 Ko binaires par image
const NB_IMG = 6;

const hits = new Map(); // repli en mémoire (par instance) si pas de KV

async function overQuota(ip) {
  const day = new Date().toISOString().slice(0, 10), key = `raccord:${day}:${ip}`;
  const { KV_REST_API_URL: u, KV_REST_API_TOKEN: t } = process.env;
  if (u && t) {
    try {
      const r = await fetch(`${u}/pipeline`, { method: 'POST', headers: { Authorization: `Bearer ${t}` }, body: JSON.stringify([['INCR', key], ['EXPIRE', key, 90000]]) });
      const j = await r.json(); return j[0].result > DAILY;
    } catch (e) { /* on retombe sur la mémoire */ }
  }
  const k = hits.get(key) || 0; hits.set(key, k + 1);
  if (hits.size > 5000) hits.clear();
  return k + 1 > DAILY;
}

function system() {
  const lines = PLAYLISTS.map(p => `- ${p.label} : ${p.mots.join(', ')}`).join('\n');
  return `Tu aides un monteur à choisir de la musique pour sa séquence vidéo. Tu vois ${NB_IMG} images réparties dans la séquence.
Choisis l'ambiance dans le vocabulaire du catalogue OSM. Playlists disponibles (nom : mots associés) :
${lines}

Réponds uniquement par un objet JSON, sans texte autour :
{"ambiances":[3 à 5 mots en français],"energie":nombre de 0 à 1,"rythme":"lent"|"moyen"|"rapide","playlists":[1 à 4 noms EXACTS pris dans la liste, du plus pertinent au moins pertinent],"mots_cles":[4 à 10 mots en français]}`;
}

function clean(o) {
  const names = new Set(PLAYLISTS.map(p => p.label));
  const arr = (a, n) => (Array.isArray(a) ? a : []).filter(s => typeof s === 'string').map(s => s.slice(0, 40)).slice(0, n);
  const e = Number(o.energie);
  return {
    ambiances: arr(o.ambiances, 5),
    energie: isFinite(e) ? Math.max(0, Math.min(1, e)) : 0.5,
    rythme: ['lent', 'moyen', 'rapide'].includes(o.rythme) ? o.rythme : 'moyen',
    playlists: arr(o.playlists, 4).filter(p => names.has(p)),
    mots_cles: arr(o.mots_cles, 10)
  };
}

module.exports = async function handler(req, res) {
  const origin = req.headers.origin || '';
  const ok = ORIGINS.includes(origin);
  if (ok) { res.setHeader('Access-Control-Allow-Origin', origin); res.setHeader('Vary', 'Origin'); }
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(ok ? 204 : 403).end();
  if (!ok) return res.status(403).json({ erreur: 'origine non autorisée' });
  if (req.method !== 'POST') return res.status(405).json({ erreur: 'POST uniquement' });
  if (!process.env.ANTHROPIC_API_KEY) return res.status(500).json({ erreur: 'relais non configuré' });

  const imgs = req.body && req.body.images;
  if (!Array.isArray(imgs) || imgs.length < 1 || imgs.length > NB_IMG) return res.status(400).json({ erreur: `1 à ${NB_IMG} images attendues` });
  for (const s of imgs) {
    if (typeof s !== 'string' || !/^[A-Za-z0-9+/=]+$/.test(s) || s.length > MAX_IMG_B64) return res.status(413).json({ erreur: 'image invalide ou trop lourde' });
  }
  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'inconnue';
  if (await overQuota(ip)) return res.status(429).json({ erreur: 'limite quotidienne atteinte' });

  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({
        model: MODEL, max_tokens: 400, system: system(),
        messages: [{ role: 'user', content: [
          ...imgs.map(data => ({ type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data } })),
          { type: 'text', text: 'Quelle musique pour cette séquence ?' }
        ] }]
      })
    });
    if (!r.ok) return res.status(502).json({ erreur: 'modèle indisponible' });
    const j = await r.json();
    const txt = (j.content || []).map(c => c.text || '').join('');
    const m = txt.match(/\{[\s\S]*\}/); if (!m) return res.status(502).json({ erreur: 'réponse illisible' });
    return res.status(200).json(clean(JSON.parse(m[0])));
  } catch (e) { return res.status(502).json({ erreur: 'réponse illisible' }); }
};
