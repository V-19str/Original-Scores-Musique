/*
 * cuesheet.js — générateur de cue sheet SACEM côté client (« Easy Cue Sheet »).
 *
 * Le monteur constitue sa sélection dans « Ma liste », saisit le contexte du
 * programme et, par titre, le timecode d'entrée et la durée d'utilisation.
 * Le PDF produit reprend les colonnes attendues par une déclaration SACEM.
 *
 * Compositeurs et clés de répartition viennent de la table Supabase `credits`,
 * dont la lecture est réservée aux comptes authentifiés (RLS). Un visiteur non
 * connecté peut quand même produire un cue sheet : les colonnes compositeur
 * sortent vides, à compléter à la main. On ne devine jamais un ayant droit.
 *
 * Dépend de : assets/vendor/jspdf.umd.min.js + jspdf.plugin.autotable.min.js,
 * et de window.osmApp exposé par index.html.
 */
(function () {
  'use strict';

  var TC_RE = /^(\d{1,2}):([0-5]\d):([0-5]\d)(?:[:.](\d{1,2}))?$/; // HH:MM:SS[:FF]
  // Deux écritures acceptées pour une durée, volontairement distinctes :
  // « 1:23 » (M:SS, secondes bornées à 59) et « 83 » (secondes nues). Une seule
  // regex permissive accepterait « 2:75 », qui n'a pas de sens.
  var DUR_MMSS_RE = /^(\d{1,3}):([0-5]\d)$/;
  var DUR_SECS_RE = /^(\d{1,4})$/;

  var creditsCache = null;   // track_id -> [{nom, cle}]
  var rows = [];             // lignes du formulaire, alignées sur la file

  function t(fr) { return (window.osmT ? window.osmT(fr) : fr); }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ── Durées et timecodes ────────────────────────────────────────────────── */

  // « 1:23 » ou « 83 » -> 83 secondes. null si la saisie n'est pas exploitable.
  function parseDuration(v) {
    var s = String(v == null ? '' : v).trim();
    var m = DUR_MMSS_RE.exec(s);
    if (m) return (parseInt(m[1], 10) * 60) + parseInt(m[2], 10);
    m = DUR_SECS_RE.exec(s);
    if (m) return parseInt(m[1], 10);
    return null;
  }

  function parseTimecode(v) {
    var m = TC_RE.exec(String(v || '').trim());
    if (!m) return null;
    return (parseInt(m[1], 10) * 3600) + (parseInt(m[2], 10) * 60) + parseInt(m[3], 10);
  }

  function fmtDuration(secs) {
    if (secs == null) return '';
    var s = Math.max(0, Math.round(secs));
    return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
  }

  function fmtTimecode(secs) {
    if (secs == null) return '';
    var s = Math.max(0, Math.round(secs));
    return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60]
      .map(function (n) { return String(n).padStart(2, '0'); }).join(':');
  }

  /* ── Crédits (Supabase, réservés aux comptes connectés) ─────────────────── */

  async function loadCredits(ids) {
    if (creditsCache) return creditsCache;
    creditsCache = {};
    var sb = window.osmApp && window.osmApp.sb();
    var user = window.osmApp && window.osmApp.user();
    if (!sb || !user || !ids.length) return creditsCache;
    // La RLS filtre déjà côté serveur ; on borne quand même la requête aux
    // titres de la sélection plutôt que de rapatrier les 2138 lignes.
    try {
      var res = await sb.from('credits').select('track_id,parts').in('track_id', ids);
      (res.data || []).forEach(function (r) { creditsCache[r.track_id] = r.parts || []; });
    } catch (e) {
      // Table absente ou droits refusés : on continue sans crédits plutôt que
      // de bloquer la génération du document.
      creditsCache = {};
    }
    return creditsCache;
  }

  function composersOf(id) {
    var parts = (creditsCache && creditsCache[id]) || [];
    return parts.map(function (p) { return p.nom; }).join(', ');
  }

  // Affichage à l'écran : « Nom 33.33% · Nom 33.33% ».
  function sharesOf(id) {
    var parts = (creditsCache && creditsCache[id]) || [];
    return parts.map(function (p) { return p.nom + ' ' + p.cle + '%'; }).join(' · ');
  }

  // Colonne « Clés » du PDF : les pourcentages seuls, dans l'ordre de la
  // colonne « Compositeurs » juste à gauche.
  function sharesOnly(id) {
    var parts = (creditsCache && creditsCache[id]) || [];
    return parts.map(function (p) { return p.cle + '%'; }).join(' · ');
  }

  /* ── Interface ──────────────────────────────────────────────────────────── */

  function ensureModal() {
    if (document.getElementById('cue-modal')) return;
    var el = document.createElement('div');
    el.id = 'cue-modal';
    el.className = 'cue-overlay';
    el.innerHTML =
      '<div class="cue-card" role="dialog" aria-modal="true" aria-labelledby="cue-h">' +
        '<button class="cue-close" onclick="osmCueSheet.close()" aria-label="Fermer">&times;</button>' +
        '<h2 id="cue-h" class="cue-h">Cue sheet SACEM</h2>' +
        '<p class="cue-sub">Renseignez le programme, puis le timecode et la durée d\'utilisation de chaque titre.</p>' +
        '<div class="cue-note" id="cue-auth"></div>' +
        '<div class="cue-grid">' +
          '<label>Titre du programme<input id="cue-prog" type="text" placeholder="Ex : Les Docs du Week-end"></label>' +
          '<label>Épisode / numéro<input id="cue-ep" type="text" placeholder="Ex : S02E14"></label>' +
          '<label>Production<input id="cue-prod" type="text" placeholder="Société de production"></label>' +
          '<label>Diffuseur<input id="cue-diff" type="text" placeholder="Ex : France 3"></label>' +
          '<label>Date de diffusion<input id="cue-date" type="date"></label>' +
          '<label>Durée du programme<input id="cue-progdur" type="text" placeholder="M:SS"></label>' +
        '</div>' +
        '<div class="cue-rows" id="cue-rows"></div>' +
        '<div class="cue-err" id="cue-err" hidden></div>' +
        '<div class="cue-actions">' +
          '<button class="cue-btn-ghost" onclick="osmCueSheet.close()">Annuler</button>' +
          '<button class="cue-btn" id="cue-go" onclick="osmCueSheet.generate()">Télécharger le PDF</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(el);
    el.addEventListener('click', function (ev) { if (ev.target === el) close(); });
  }

  function renderRows() {
    var host = document.getElementById('cue-rows');
    host.innerHTML = rows.map(function (r, i) {
      var comp = composersOf(r.id);
      return '' +
        '<div class="cue-row">' +
          '<div class="cue-row-head">' +
            '<span class="cue-row-n">' + (i + 1) + '</span>' +
            '<span class="cue-row-t">' + esc(r.title) + '</span>' +
            '<span class="cue-row-d">' + esc(r.duration || '') + '</span>' +
          '</div>' +
          '<div class="cue-row-fields">' +
            '<label>Timecode<input type="text" inputmode="numeric" placeholder="00:00:00" ' +
              'value="' + esc(r.tc) + '" oninput="osmCueSheet.set(' + i + ',\'tc\',this.value)"></label>' +
            '<label>Durée utilisée<input type="text" inputmode="numeric" placeholder="M:SS" ' +
              'value="' + esc(r.used) + '" oninput="osmCueSheet.set(' + i + ',\'used\',this.value)"></label>' +
            '<label>Utilisation<select onchange="osmCueSheet.set(' + i + ',\'kind\',this.value)">' +
              ['Fond sonore', 'Générique début', 'Générique fin', 'Illustration', 'Thème'].map(function (k) {
                return '<option' + (r.kind === k ? ' selected' : '') + '>' + k + '</option>';
              }).join('') +
            '</select></label>' +
          '</div>' +
          '<div class="cue-row-comp">' +
            (comp
              ? '<span class="cue-ok">Compositeurs : ' + esc(sharesOf(r.id)) + '</span>'
              : '<label class="cue-missing">Compositeurs à compléter' +
                '<input type="text" placeholder="Nom Prénom 50%, Nom Prénom 50%" ' +
                'value="' + esc(r.manual) + '" oninput="osmCueSheet.set(' + i + ',\'manual\',this.value)"></label>') +
          '</div>' +
        '</div>';
    }).join('');
  }

  async function open() {
    var q = (window.osmApp && window.osmApp.queue()) || [];
    if (!q.length) {
      alert(t('Ajoutez d\'abord des morceaux à votre liste.'));
      return;
    }
    ensureModal();
    rows = q.map(function (tr) {
      return {
        id: tr.id, title: tr.title, playlist: tr.playlistLabel,
        duration: tr.duration || '',
        // Par défaut, la durée d'utilisation est la durée du morceau : c'est le
        // cas le plus courant et ça évite une saisie inutile.
        tc: '', used: tr.duration || '', kind: 'Fond sonore', manual: ''
      };
    });
    var modal = document.getElementById('cue-modal');
    modal.classList.add('show');

    var note = document.getElementById('cue-auth');
    var user = window.osmApp && window.osmApp.user();
    note.innerHTML = user
      ? ''
      : '⚠ ' + esc(t('Vous n\'êtes pas connecté : les compositeurs ne peuvent pas être pré-remplis. Connectez-vous pour un cue sheet complet.'));
    note.hidden = !!user;

    // Premier rendu immédiat (la liste peut être longue, on n'attend pas le
    // réseau), puis second rendu une fois les crédits connus. Le
    // MutationObserver d'i18n.js traduit le contenu injecté si on est en EN.
    renderRows();
    await loadCredits(rows.map(function (r) { return r.id; }));
    renderRows();
  }

  function close() {
    var m = document.getElementById('cue-modal');
    if (m) m.classList.remove('show');
  }

  function set(i, field, value) {
    if (rows[i]) rows[i][field] = value;
  }

  /* ── PDF ────────────────────────────────────────────────────────────────── */

  function validate() {
    var errs = [];
    if (!document.getElementById('cue-prog').value.trim()) {
      errs.push(t('Le titre du programme est obligatoire.'));
    }
    rows.forEach(function (r, i) {
      if (r.tc && parseTimecode(r.tc) === null) {
        errs.push(t('Ligne') + ' ' + (i + 1) + ' : ' + t('timecode attendu au format HH:MM:SS.'));
      }
      if (r.used && parseDuration(r.used) === null) {
        errs.push(t('Ligne') + ' ' + (i + 1) + ' : ' + t('durée attendue au format M:SS.'));
      }
    });
    return errs;
  }

  function generate() {
    var errs = validate();
    var box = document.getElementById('cue-err');
    if (errs.length) {
      box.innerHTML = errs.map(function (e) { return esc(e); }).join('<br>');
      box.hidden = false;
      box.scrollIntoView({ block: 'nearest' });
      return;
    }
    box.hidden = true;

    var jsPDFCtor = window.jspdf && window.jspdf.jsPDF;
    if (!jsPDFCtor) {
      box.textContent = t('Le module PDF n\'a pas pu être chargé. Rechargez la page.');
      box.hidden = false;
      return;
    }

    var prog = document.getElementById('cue-prog').value.trim();
    var doc = new jsPDFCtor({ orientation: 'landscape', unit: 'mm', format: 'a4' });

    doc.setFontSize(15);
    doc.text('Cue sheet — ' + prog, 14, 16);

    doc.setFontSize(9);
    var meta = [
      ['Épisode', document.getElementById('cue-ep').value.trim()],
      ['Production', document.getElementById('cue-prod').value.trim()],
      ['Diffuseur', document.getElementById('cue-diff').value.trim()],
      ['Diffusion', document.getElementById('cue-date').value.trim()],
      ['Durée programme', document.getElementById('cue-progdur').value.trim()]
    ].filter(function (p) { return p[1]; })
     .map(function (p) { return p[0] + ' : ' + p[1]; }).join('     ');
    if (meta) doc.text(meta, 14, 23);

    var total = 0;
    var body = rows.map(function (r, i) {
      var used = parseDuration(r.used);
      if (used != null) total += used;
      return [
        i + 1,
        r.title,
        r.playlist || '',
        r.tc ? fmtTimecode(parseTimecode(r.tc)) : '',
        used != null ? fmtDuration(used) : '',
        r.kind || '',
        composersOf(r.id) || r.manual || '',
        sharesOnly(r.id)
      ];
    });

    doc.autoTable({
      startY: meta ? 28 : 22,
      head: [['#', 'Titre', 'Playlist', 'Timecode', 'Durée', 'Utilisation', 'Compositeurs', 'Clés']],
      body: body,
      styles: { fontSize: 7.5, cellPadding: 1.6, overflow: 'linebreak' },
      headStyles: { fillColor: [255, 85, 0], textColor: 255, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [248, 248, 248] },
      columnStyles: {
        0: { cellWidth: 8, halign: 'right' },
        3: { cellWidth: 20 }, 4: { cellWidth: 14 },
        5: { cellWidth: 24 }, 7: { cellWidth: 30 }
      },
      // Le pied de page se répète à chaque page : un cue sheet passe rarement
      // sur une seule feuille et la SACEM demande une pagination lisible.
      didDrawPage: function (data) {
        var page = doc.internal.getNumberOfPages();
        doc.setFontSize(7.5);
        doc.setTextColor(120);
        doc.text('Original Scores Music — osm-music.fr', data.settings.margin.left,
                 doc.internal.pageSize.getHeight() - 8);
        doc.text('Page ' + page, doc.internal.pageSize.getWidth() - 24,
                 doc.internal.pageSize.getHeight() - 8);
        doc.setTextColor(0);
      }
    });

    doc.setFontSize(9);
    doc.text(rows.length + ' titre(s) — durée totale utilisée : ' + fmtDuration(total),
             14, doc.lastAutoTable.finalY + 8);

    var missing = rows.filter(function (r) { return !composersOf(r.id) && !r.manual.trim(); }).length;
    if (missing) {
      doc.setTextColor(180, 60, 0);
      // Pas d'emoji ici : les polices standard de jsPDF sont encodees en
      // WinAnsi, un « ⚠ » y sort en caractere parasite avec un espacement
      // casse. Les accents, eux, passent sans probleme.
      doc.text('Attention : ' + missing +
               ' titre(s) sans compositeur, à compléter avant dépôt SACEM.',
               14, doc.lastAutoTable.finalY + 14);
      doc.setTextColor(0);
    }

    // Même normalisation que plSlug() dans index.html.
    var slug = prog.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'cue-sheet';
    doc.save('cue-sheet-' + slug + '.pdf');
  }

  window.osmCueSheet = {
    open: open, close: close, set: set, generate: generate,
    // exposés pour les tests
    _parseDuration: parseDuration, _parseTimecode: parseTimecode,
    _fmtDuration: fmtDuration, _fmtTimecode: fmtTimecode
  };
})();
