/* Format compact des analyses par titre, partagé par le script Node et la page web.
   Un seul codage/décodage : sinon les calages ne correspondraient pas. */
(function (root) {
  const VERSION = 1;

  /* R : sortie de analyzeRhythm. Renvoie l'objet JSON stocké dans analyses/<id>.json */
  function encode(R) {
    const n = R.feats.length;
    const e = [], c = [], h = [];
    for (let k = 0; k < n; k++) {
      const f = R.feats[k];
      e.push(Math.round(f.db * 10) / 10);
      c.push(Math.round(f.cent));
      let s = ''; for (let q = 0; q < 12; q++) s += Math.min(9, Math.max(0, Math.round(f.ch[q] * 9)));
      h.push(s);
    }
    return {
      v: VERSION, bpm: Math.round(R.bpm * 100) / 100, p: R.p, b0: R.bars.length ? R.bars[0] : 0,
      barDur: R.barDur, n, E: R.E, dur: R.duration, conf: Math.round(R.confidence * 100) / 100,
      e, c, h: h.join(',')
    };
  }

  /* Reconstruit l'objet R attendu par fitTrack */
  function decode(a) {
    if (a.v !== VERSION) throw new Error('Version d’analyse inconnue : ' + a.v);
    const hs = a.h ? a.h.split(',') : [];
    const bars = [], feats = [];
    let t = a.b0;
    for (let k = 0; k < a.n; k++, t += a.barDur) {
      bars.push(t);
      const ch = new Float32Array(12); let nrm = 0;
      for (let q = 0; q < 12; q++) { ch[q] = +hs[k][q] / 9; nrm += ch[q] * ch[q]; }
      nrm = Math.sqrt(nrm) || 1; for (let q = 0; q < 12; q++) ch[q] /= nrm;
      feats.push({ db: a.e[k], cent: a.c[k], ch });
    }
    return { bpm: a.bpm, p: a.p, barDur: a.barDur, bars, feats, E: a.E, duration: a.dur, confidence: a.conf };
  }

  /* Profil d'énergie résumé en 8 valeurs (0 à 1) pour la présélection */
  function energyProfile(a, parts) {
    parts = parts || 8; const out = [];
    if (!a.n) return new Array(parts).fill(0);
    const lo = -60, hi = 0;
    for (let q = 0; q < parts; q++) {
      const i0 = Math.floor(q * a.n / parts), i1 = Math.max(i0 + 1, Math.floor((q + 1) * a.n / parts));
      let s = 0; for (let i = i0; i < i1 && i < a.n; i++) s += a.e[i];
      s /= (Math.min(i1, a.n) - i0);
      out.push(Math.round(Math.max(0, Math.min(1, (s - lo) / (hi - lo))) * 100) / 100);
    }
    return out;
  }

  const api = { VERSION, encode, decode, energyProfile };
  if (typeof module !== 'undefined') module.exports = api; else root.RaccordFormat = api;
})(typeof self !== 'undefined' ? self : this);
