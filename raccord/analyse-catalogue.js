#!/usr/bin/env node
/* Phase 2 : analyse de tout le catalogue, une fois. Reprenable.
   Usage : node raccord/analyse-catalogue.js [--limit N] [--force] [--concurrency N]
                                              [--catalogue chemin] [--out dossier] [--ids a,b]
   Décodage : ffmpeg, mono 22 050 Hz flottant. Même moteur que la page web. */
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const engine = require('./raccord-engine.js'), fmt = require('./analysis-format.js');

const arg = (n, d) => { const i = process.argv.indexOf('--' + n); return i < 0 ? d : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true); };
const ROOT = path.join(__dirname, '..');
const CAT = arg('catalogue', path.join(ROOT, 'catalogue.json'));
const OUT = arg('out', __dirname), AN = path.join(OUT, 'analyses');
const LIMIT = +arg('limit', 0), FORCE = !!arg('force', false), CONC = +arg('concurrency', 3);
const IDS = arg('ids', '') ? String(arg('ids')).split(',') : null;
const SR = 22050, MIN_DUR = 45, CONF_LOW = 2; // CONF_LOW à calibrer à l'oreille avec Vlad

function decode(url) {
  return new Promise((res, rej) => {
    const ff = spawn('ffmpeg', ['-v', 'error', '-i', url, '-ac', '1', '-ar', String(SR), '-f', 'f32le', '-']);
    const chunks = []; let err = '';
    ff.stdout.on('data', d => chunks.push(d)); ff.stderr.on('data', d => err += d);
    ff.on('error', rej);
    ff.on('close', code => {
      if (code !== 0) return rej(new Error('ffmpeg : ' + err.trim().slice(0, 200)));
      const b = Buffer.concat(chunks); if (b.length < 4) return rej(new Error('audio vide'));
      res(new Float32Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.length - (b.length % 4))));
    });
  });
}

async function analyseOne(tr) {
  const x = await decode(tr.url);
  const A = engine.analyzeSignal(x, SR);
  const R = engine.analyzeRhythm(A);
  return fmt.encode(R);
}

function buildIndex(tracks) {
  const rows = [];
  for (const tr of tracks) {
    const f = path.join(AN, tr.id + '.json'); if (!fs.existsSync(f)) continue;
    let a; try { a = JSON.parse(fs.readFileSync(f, 'utf8')); fmt.decode(a); } catch (e) { continue; }
    const mean = a.n ? a.e.reduce((s, v) => s + v, 0) / a.n : -60;
    rows.push({
      id: tr.id, t: tr.title, bpm: Math.round(a.bpm), d: Math.round(a.E), c: a.conf,
      en: Math.round(Math.max(0, Math.min(1, (mean + 60) / 60)) * 100) / 100,
      pf: fmt.energyProfile(a), pl: tr.playlist, tg: (tr.tags || []).slice(0, 6), u: tr.url
    });
  }
  fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(rows));
  const faibles = rows.filter(r => r.c < CONF_LOW), courts = rows.filter(r => r.d < MIN_DUR);
  const md = `# Rapport d'analyse du catalogue\n\n- Titres analysés : **${rows.length}** sur ${tracks.length}\n- Pulsation faible (confidence < ${CONF_LOW}, seuil à calibrer) : **${faibles.length}**\n- Trop courts (< ${MIN_DUR} s utiles) : **${courts.length}**\n\n## Pulsation faible\n\n${faibles.map(r => `- ${r.id} (${r.t}) : conf ${r.c}, ${r.bpm} BPM`).join('\n') || '_aucun_'}\n\n## Trop courts\n\n${courts.map(r => `- ${r.id} (${r.t}) : ${r.d} s`).join('\n') || '_aucun_'}\n`;
  fs.writeFileSync(path.join(OUT, 'rapport-analyse.md'), md);
  return rows.length;
}

(async () => {
  const cat = JSON.parse(fs.readFileSync(CAT, 'utf8')).tracks;
  fs.mkdirSync(AN, { recursive: true });
  let todo = cat.filter(t => t.url && (!IDS || IDS.includes(t.id)) && (FORCE || !fs.existsSync(path.join(AN, t.id + '.json'))));
  if (LIMIT) todo = todo.slice(0, LIMIT);
  console.log(`${todo.length} titre(s) à analyser (${cat.length} au catalogue).`);
  let done = 0, fail = 0; const errs = [];
  const q = todo.slice();
  await Promise.all(Array.from({ length: CONC }, async () => {
    for (let tr; (tr = q.shift());) {
      try {
        const a = await analyseOne(tr);
        fs.writeFileSync(path.join(AN, tr.id + '.json.tmp'), JSON.stringify(a));
        fs.renameSync(path.join(AN, tr.id + '.json.tmp'), path.join(AN, tr.id + '.json'));
        done++;
      } catch (e) { fail++; errs.push(tr.id + ' : ' + e.message); }
      if ((done + fail) % 25 === 0) console.log(`${done + fail}/${todo.length}`);
    }
  }));
  const n = buildIndex(cat);
  if (errs.length) fs.writeFileSync(path.join(OUT, 'erreurs-analyse.txt'), errs.join('\n') + '\n');
  console.log(`Terminé : ${done} analysés, ${fail} en erreur. index.json : ${n} lignes.`);
})();
