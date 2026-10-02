/* ===== Raccord : moteur d'analyse et de calage (sans DOM) ===== */
const FFT_N = 1024, HOP = 512;

function makeFFT(n) {
  const rev = new Uint32Array(n), bits = Math.log2(n);
  for (let i = 0; i < n; i++) { let r = 0, x = i; for (let b = 0; b < bits; b++) { r = (r << 1) | (x & 1); x >>= 1; } rev[i] = r; }
  const cs = new Float32Array(n / 2), sn = new Float32Array(n / 2);
  for (let i = 0; i < n / 2; i++) { cs[i] = Math.cos(2 * Math.PI * i / n); sn[i] = -Math.sin(2 * Math.PI * i / n); }
  return function (re, im) {
    for (let i = 0; i < n; i++) { const j = rev[i]; if (j > i) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
    for (let size = 2; size <= n; size <<= 1) {
      const half = size >> 1, step = n / size;
      for (let i = 0; i < n; i += size) {
        for (let k = 0; k < half; k++) {
          const wr = cs[k * step], wi = sn[k * step], a = i + k, b = a + half;
          const tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr;
          re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
        }
      }
    }
  };
}

/* x : signal mono, sr : fréquence d'échantillonnage */
function analyzeSignal(x, sr) {
  const n = FFT_N, hop = HOP, fft = makeFFT(n), nb = n / 2;
  const win = new Float32Array(n);
  for (let i = 0; i < n; i++) win[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1));
  const frames = Math.max(1, Math.floor((x.length - n) / hop) + 1);
  const re = new Float32Array(n), im = new Float32Array(n);
  let prev = new Float32Array(nb), cur = new Float32Array(nb);
  const flux = new Float32Array(frames), low = new Float32Array(frames), rms = new Float32Array(frames),
    cent = new Float32Array(frames), chroma = new Float32Array(frames * 12);
  const binHz = sr / n, lowBin = Math.max(2, Math.round(180 / binHz));
  const pc = new Int8Array(nb).fill(-1);
  for (let k = 1; k < nb; k++) { const f = k * binHz; if (f >= 65 && f <= 2100) pc[k] = (((Math.round(12 * Math.log2(f / 440)) + 69) % 12) + 12) % 12; }
  for (let f = 0; f < frames; f++) {
    const off = f * hop; let e = 0;
    for (let i = 0; i < n; i++) { const v = x[off + i] || 0; e += v * v; re[i] = v * win[i]; im[i] = 0; }
    rms[f] = Math.sqrt(e / n);
    fft(re, im);
    let fl = 0, lf = 0, num = 0, den = 0;
    for (let k = 1; k < nb; k++) {
      const m = Math.hypot(re[k], im[k]), lm = Math.log1p(100 * m);
      cur[k] = lm; const d = lm - prev[k];
      if (d > 0) { fl += d; if (k <= lowBin) lf += d; }
      num += k * m; den += m;
      if (pc[k] >= 0) chroma[f * 12 + pc[k]] += m;
    }
    flux[f] = f === 0 ? 0 : fl; low[f] = f === 0 ? 0 : lf;
    cent[f] = den > 0 ? num / den * binHz : 0;
    const t = prev; prev = cur; cur = t;
  }
  return { sr, fr: sr / hop, t0: n / 2 / sr, frames, flux, low, rms, cent, chroma, duration: x.length / sr };
}

function onsetEnv(arr, fr) {
  const n = arr.length, w = Math.max(1, Math.round(fr * 0.25)), ps = new Float64Array(n + 1);
  for (let i = 0; i < n; i++) ps[i + 1] = ps[i] + arr[i];
  const o = new Float32Array(n);
  for (let i = 0; i < n; i++) { const a = Math.max(0, i - w), b = Math.min(n, i + w + 1); o[i] = Math.max(0, arr[i] - (ps[b] - ps[a]) / (b - a)); }
  return o;
}

/* Tempo, grille des temps et des mesures, fin musicale, empreinte par mesure */
function analyzeRhythm(A) {
  const { fr, frames } = A;
  const o = onsetEnv(A.flux, fr), ol = onsetEnv(A.low, fr);
  const minL = Math.floor(fr * 60 / 190), maxL = Math.ceil(fr * 60 / 60);
  let bestL = minL, bestV = -Infinity; const ac = new Float64Array(maxL + 2);
  for (let L = minL; L <= maxL + 1; L++) {
    let s = 0; for (let i = 0; i + L < frames; i++) s += o[i] * o[i + L];
    s /= Math.max(1, frames - L); const bpm = 60 * fr / L;
    ac[L] = s * Math.exp(-0.5 * Math.pow(Math.log2(bpm / 115) / 0.8, 2));
  }
  for (let L = minL; L <= maxL; L++) if (ac[L] > bestV) { bestV = ac[L]; bestL = L; }
  let Lr = bestL;
  if (bestL > minL && bestL < maxL) { const a = ac[bestL - 1], b = ac[bestL], c = ac[bestL + 1], d = a - 2 * b + c; if (d !== 0) Lr = bestL + 0.5 * (a - c) / d; }
  const p0 = Lr / fr;
  const T0 = A.t0 || 0;
  const at = (arr, t) => { const x = (t - T0) * fr, i = Math.floor(x); if (i < 0 || i + 1 >= frames) return 0; const f = x - i; return arr[i] * (1 - f) + arr[i + 1] * f; };
  let best = { s: -Infinity, p: p0, ph: 0 };
  for (let d = -25; d <= 25; d++) {
    const p = p0 * (1 + d * 0.0008);
    for (let ph = 0; ph < p; ph += 1 / fr) {
      let s = 0, c = 0;
      for (let t = ph; t < A.duration; t += p) { s += at(o, t); c++; }
      s /= Math.max(1, c);
      if (s > best.s) best = { s, p, ph };
    }
  }
  let meanO = 0; for (let i = 0; i < frames; i++) meanO += o[i]; meanO /= Math.max(1, frames);
  const confidence = best.s / (meanO + 1e-9); // > ~2 : pulsation nette ; à calibrer sur le catalogue
  const p = best.p, ph = best.ph;
  let bm = 0, bv = -Infinity;
  for (let m = 0; m < 4; m++) {
    let s = 0;
    for (let t = ph + m * p; t < A.duration; t += 4 * p) s += at(ol, t) + 0.3 * at(o, t);
    if (s > bv) { bv = s; bm = m; }
  }
  const barDur = 4 * p, firstDown = ph + bm * p;
  const b0 = firstDown - barDur * Math.ceil(firstDown / barDur - 1e-9);
  let mx = 0; for (let f = 0; f < frames; f++) if (A.rms[f] > mx) mx = A.rms[f];
  let lastF = frames - 1; while (lastF > 0 && A.rms[lastF] < mx * 0.012) lastF--;
  const E = Math.min(A.duration, (lastF * HOP + FFT_N) / A.sr);
  const bars = []; for (let t = b0; t < E - 0.25 * barDur; t += barDur) bars.push(t);
  const feats = bars.map(t => {
    const f0 = Math.max(0, Math.floor((t - T0) * fr)), f1 = Math.min(frames, Math.floor((t + barDur - T0) * fr));
    const ch = new Float32Array(12); let r = 0, c = 0, cnt = 0;
    for (let f = f0; f < f1; f++) { r += A.rms[f]; c += A.cent[f]; cnt++; for (let k = 0; k < 12; k++) ch[k] += A.chroma[f * 12 + k]; }
    let nrm = 0; for (let k = 0; k < 12; k++) nrm += ch[k] * ch[k]; nrm = Math.sqrt(nrm) || 1;
    for (let k = 0; k < 12; k++) ch[k] /= nrm;
    return { db: 20 * Math.log10((cnt ? r / cnt : 0) + 1e-5), cent: cnt ? c / cnt : 0, ch };
  });
  return { bpm: 60 / p, p, barDur, bars, feats, E, duration: A.duration, confidence };
}

function barDist(a, b, centRef) {
  let dot = 0; for (let k = 0; k < 12; k++) dot += a.ch[k] * b.ch[k];
  const cd = 1 - Math.max(0, Math.min(1, dot));
  const ed = Math.min(1, Math.abs(a.db - b.db) / 12);
  const kd = Math.min(1, Math.abs(a.cent - b.cent) / (centRef || 1));
  return 0.55 * cd + 0.3 * ed + 0.15 * kd;
}

const mod4 = x => ((x % 4) + 4) % 4;

function pearson(a, b) {
  const n = a.length; if (n < 3) return 0;
  let ma = 0, mb = 0; for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; } ma /= n; mb /= n;
  let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; sab += x * y; saa += x * x; sbb += y * y; }
  return saa > 1e-9 && sbb > 1e-9 ? sab / Math.sqrt(saa * sbb) : 0;
}

/* V : { D, cuts:[{t,w}], vAt(t0,t1) } — R : analyse rythmique d'un morceau */
function fitTrack(R, V) {
  const D = V.D, bd = R.barDur, p = R.p, bs = R.bars, N = bs.length, F = R.feats, E = R.E;
  if (N < 2) return null;
  let centRef = 0; F.forEach(f => centRef += f.cent); centRef = (centRef / N) || 1;
  const tailRoom = Math.min(1.5, Math.max(0, (E - bs[N - 1]) * 0.6));
  const cuts = V.cuts.filter(c => c.t > 0.3 && c.t < D - 0.3);
  const asl = D / (V.cuts.length + 1), ratio = asl / bd;
  const pace = Math.exp(-0.5 * Math.pow(Math.log2(ratio / 1.5) / 1.2, 2));
  const junction = (i, j) => {
    if (j === i + 1) return 0;
    const c1 = i + 1 < N ? barDist(F[i + 1], F[j], centRef) : 0.6;
    const c2 = j - 1 >= 0 && i >= 0 ? barDist(F[i], F[j - 1], centRef) : 0.6;
    let c = (c1 + c2) / 2; if (mod4(i + 1 - j) !== 0) c += 0.25;
    return Math.min(1, c);
  };
  // La synchro ne dépend que du décalage de départ : on la précalcule.
  const STEP = 0.01, nOff = Math.ceil(bd / STEP);
  const syncTab = new Float32Array(nOff), hitTab = new Int16Array(nOff);
  let swTot = 0; cuts.forEach(c => swTot += c.w);
  for (let q = 0; q < nOff; q++) {
    const off = q * STEP; let ss = 0, hits = 0;
    for (const c of cuts) {
      if (c.t < off - 0.05) continue;
      const rel = (c.t - off) / p, n = Math.round(rel), d = Math.abs(rel - n) * p;
      ss += c.w * Math.exp(-Math.pow(d / 0.07, 2)) * (mod4(n) === 0 ? 1.15 : 1);
      if (d < 0.09) hits++;
    }
    syncTab[q] = swTot ? Math.min(1, ss / swTot) : 0.5; hitTab[q] = hits;
  }
  const EARLY = 1.0;
  let best = null;
  const vCache = new Map();
  for (let s = 0; s < N; s++) {
    for (let i = s - 1; i < N - 1; i++) {
      const aLen = (i + 1 - s) * bd;
      const lo = E - D - tailRoom + aLen, hi = E - D + EARLY + aLen + bd;
      const j0 = Math.max(0, Math.ceil((lo - bs[0]) / bd - 1e-9)), j1 = Math.min(N - 1, Math.floor((hi - bs[0]) / bd + 1e-9));
      for (let j = j0; j <= j1; j++) {
        if (i === s - 1 && j !== s) continue;
        const Tm = aLen + (E - bs[j]);
        const oLo = Math.max(0, D - EARLY - Tm), oHi = Math.min(bd - STEP, D + tailRoom - Tm);
        if (oHi < oLo) continue;
        let bq = -1, bv = -Infinity;
        for (let q = Math.ceil(oLo / STEP); q * STEP <= oHi + 1e-9 && q < nOff; q++) {
          const off = q * STEP, gap = Math.max(0, D - (off + Tm));
          const v = 0.33 * syncTab[q] - 0.05 * gap - 0.04 * (off / bd);
          if (v > bv) { bv = v; bq = q; }
        }
        if (bq < 0) continue;
        const off = bq * STEP, sync = syncTab[bq], hits = hitTab[bq];
        const jc = junction(i, j);
        const seq = []; for (let k = s; k <= i; k++) seq.push(k); for (let k = j; k < N; k++) seq.push(k);
        const ae = [], ve = [];
        for (let m = 0; m < seq.length; m++) {
          const t0 = off + m * bd; if (t0 >= D - 0.2) break;
          const key = Math.round(t0 * 100);
          let v = vCache.get(key); if (v === undefined) { v = V.vAt(t0, Math.min(D, t0 + bd)); vCache.set(key, v); }
          ae.push(F[seq[m]].db); ve.push(v);
        }
        const corr = pearson(ae, ve);
        const sb = s === 0 ? 0.05 : (mod4(s) === 0 ? 0.02 : -0.03);
        const score = bv + 0.32 * (1 - jc) + 0.25 * ((corr + 1) / 2) + 0.10 * pace + sb - (j !== i + 1 && jc > 0.55 ? 0.08 : 0) - (j <= i ? 0.04 : 0);
        if (!best || score > best.score) best = { score, s, i, j, off, over: off + Tm - D, gap: Math.max(0, D - off - Tm), junction: jc, sync, hits, cutsCount: cuts.length, corr, edit: j === i + 1 ? 'none' : (j > i + 1 ? 'skip' : 'repeat') };
      }
    }
  }
  return best;
}

/* Assemble les échantillons d'un canal ; renvoie des Float32Array */
function renderChannels(chData, sr, R, fit, D) {
  const len = Math.round(D * sr), bs = R.bars, bd = R.barDur, srcLen = chData[0].length;
  const out = chData.map(() => new Float32Array(len));
  const aLen = (fit.i + 1 - fit.s) * bd;
  const segs = [];
  if (fit.i >= fit.s) segs.push({ s0: bs[fit.s], s1: bs[fit.i + 1], dst: fit.off });
  segs.push({ s0: bs[fit.j], s1: srcLen / sr, dst: fit.off + (fit.i >= fit.s ? aLen : 0) });
  const pre = fit.off;
  if (pre > 0) { segs[0].s0 -= pre; segs[0].dst -= pre; }
  const XF = Math.round(0.03 * sr), FI = Math.round(0.004 * sr), PF = Math.round(Math.min(pre, 0.5) * sr);
  segs.forEach((g, gi) => {
    const isLast = gi === segs.length - 1;
    const srcStart = Math.round(g.s0 * sr), dstStart = Math.round(g.dst * sr);
    const count = Math.round((g.s1 - g.s0) * sr) + (isLast ? 0 : XF);
    const body = count - (isLast ? 0 : XF);
    for (let c = 0; c < chData.length; c++) {
      const src = chData[c], o = out[c];
      for (let k = 0; k < count; k++) {
        const d = dstStart + k; if (d < 0 || d >= len) continue;
        const si = srcStart + k; const v = si >= 0 && si < srcLen ? src[si] : 0;
        let gn = 1;
        if (gi === 0 && pre > 0 && k < PF) gn *= Math.sin(0.5 * Math.PI * k / PF);
        if (gi > 0 && k < FI) gn *= k / FI;
        if (!isLast && k >= body) gn *= Math.cos(0.5 * Math.PI * (k - body) / XF);
        o[d] += v * gn;
      }
    }
  });
  const fo = Math.round((fit.over > 0.02 ? 0.6 : 0.012) * sr);
  for (const o of out) for (let k = 0; k < fo && k < len; k++) o[len - 1 - k] *= k / fo;
  return out;
}

function audibleSpan(chs, sr) {
  const n = chs[0].length; let a = 0, b = n - 1;
  const loud = i => chs.some(c => Math.abs(c[i]) > 1e-3);
  while (a < n && !loud(a)) a++; while (b > a && !loud(b)) b--;
  return a >= n ? [0, 0] : [a / sr, (b + 1) / sr];
}

if (typeof module !== 'undefined') module.exports = { analyzeSignal, analyzeRhythm, fitTrack, renderChannels, audibleSpan };
