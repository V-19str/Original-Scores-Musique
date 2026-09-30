/**
 * main.js — logique du panneau CEP "OSM — Original Scores Music"
 */
(function () {
  'use strict';

  /* ── Config ─────────────────────────────────────────────────────────────── */
  var CATALOGUE_URL = 'https://osm-music.fr/catalogue.json';
  var SB_URL        = 'https://ubpmzncfhkohoyfonjbb.supabase.co';
  var SB_KEY        = 'sb_publishable_8rWkPwFktGZLsk79WCq7PQ_3Gb1xykh';
  var DOWNLOAD_DIR  = ''; // rempli par CSInterface à l'init

  /* ── État ────────────────────────────────────────────────────────────────── */
  var allTracks    = [];
  var filtered     = [];
  var activeIdx    = -1;
  var activeFilter = 'all';
  var searchQuery  = '';
  var sbSession    = null; // { access_token, user: { email } }
  var creditsCache = {};

  /* ── Supabase fetch helper ───────────────────────────────────────────────── */
  function sbFetch(path, opts) {
    var headers = Object.assign({ apikey: SB_KEY, 'Content-Type': 'application/json' }, opts && opts.headers);
    if (sbSession) headers['Authorization'] = 'Bearer ' + sbSession.access_token;
    return fetch(SB_URL + path, Object.assign({}, opts, { headers: headers }));
  }

  /* ── Chargement du catalogue ─────────────────────────────────────────────── */
  function loadCatalogue() {
    showState('<div class="spinner"></div><br>Chargement du catalogue…');
    fetch(CATALOGUE_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var tracks = (data.tracks || []).filter(function (t) { return t.playlist !== 'samples'; });
        // Fusionne les nouveaux titres Supabase (lecture publique)
        return sbFetch('/rest/v1/nouveaux_titres?select=*')
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (rows) {
            var known = new Set(tracks.map(function (t) { return t.id; }));
            rows.forEach(function (n) {
              if (!n.track_id || known.has(n.track_id)) return;
              tracks.push({ id: n.track_id, title: n.title, playlist: n.playlist,
                duration: n.duration || '', url: n.url, tags: n.tags || [], bpm: n.bpm });
            });
            return tracks;
          });
      })
      .then(function (tracks) {
        allTracks = tracks;
        filtered  = tracks.slice();
        renderTracks();
        renderFilterChips();
      })
      .catch(function () {
        showState('Erreur de chargement.<br>Vérifiez votre connexion.');
      });
  }

  /* ── Recherche / filtres ─────────────────────────────────────────────────── */
  function applyFilters() {
    var q = searchQuery.toLowerCase();
    filtered = allTracks.filter(function (t) {
      var matchQuery = !q ||
        t.title.toLowerCase().includes(q) ||
        (t.playlist || '').toLowerCase().includes(q) ||
        (t.tags || []).some(function (tag) { return tag.toLowerCase().includes(q); });
      var matchFilter = activeFilter === 'all' || t.playlist === activeFilter;
      return matchQuery && matchFilter;
    });
    activeIdx = -1;
    renderTracks();
  }

  function getPlaylists() {
    var seen = {};
    var pls  = [];
    allTracks.forEach(function (t) {
      if (t.playlist && !seen[t.playlist]) {
        seen[t.playlist] = true;
        pls.push(t.playlist);
      }
    });
    return pls.sort();
  }

  /* ── Rendu liste ─────────────────────────────────────────────────────────── */
  function renderTracks() {
    var list = document.getElementById('track-list');
    if (!filtered.length) {
      list.innerHTML = '<div class="state-msg">Aucun résultat.</div>';
      return;
    }
    list.innerHTML = filtered.map(function (t, i) {
      var isActive = i === activeIdx;
      var tags = (t.tags || []).slice(0, 3).map(function (tag) {
        return '<span class="tag-pill">' + esc(tag) + '</span>';
      }).join('');
      return '<div class="track-item' + (isActive ? ' active' : '') + '" data-idx="' + i + '">' +
        '<div class="play-btn" data-idx="' + i + '">' + (isActive && !audio.paused ? '⏸' : '▶') + '</div>' +
        '<div class="track-info">' +
          '<div class="track-title">' + esc(t.title) + '</div>' +
          '<div class="track-meta">' + esc(labelOf(t.playlist)) +
            (t.bpm ? ' · ' + t.bpm + ' BPM' : '') + '</div>' +
          (tags ? '<div class="tag-row">' + tags + '</div>' : '') +
        '</div>' +
        '<div class="track-duration">' + esc(t.duration || '') + '</div>' +
      '</div>';
    }).join('');

    list.querySelectorAll('.track-item').forEach(function (el) {
      el.addEventListener('click', function (ev) {
        var idx = parseInt(el.getAttribute('data-idx'), 10);
        if (ev.target.classList.contains('play-btn') || ev.target.closest('.play-btn')) {
          togglePlay(idx);
        } else {
          selectTrack(idx);
        }
      });
    });
  }

  function renderFilterChips() {
    var bar = document.getElementById('filters');
    var pls = getPlaylists();
    bar.innerHTML = '<div class="filter-chip' + (activeFilter === 'all' ? ' active' : '') +
      '" data-pl="all">Tout</div>' +
      pls.map(function (pl) {
        return '<div class="filter-chip' + (activeFilter === pl ? ' active' : '') +
          '" data-pl="' + esc(pl) + '">' + esc(labelOf(pl)) + '</div>';
      }).join('');
    bar.querySelectorAll('.filter-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        activeFilter = chip.getAttribute('data-pl');
        applyFilters();
        renderFilterChips();
      });
    });
  }

  /* ── Audio ───────────────────────────────────────────────────────────────── */
  var audio = new Audio();
  audio.crossOrigin = 'anonymous';

  audio.addEventListener('timeupdate', updateProgress);
  audio.addEventListener('ended', function () { updateProgress(); renderTracks(); });
  audio.addEventListener('loadedmetadata', function () { updateProgress(); });

  function togglePlay(idx) {
    if (activeIdx === idx && !audio.paused) {
      audio.pause();
      renderTracks();
      return;
    }
    selectTrack(idx);
    audio.play().catch(function () {});
  }

  function selectTrack(idx) {
    var t = filtered[idx];
    if (!t) return;
    activeIdx = idx;
    if (audio.src !== t.url) {
      audio.src = t.url;
    }
    renderTracks();
    showPlayer(t);
  }

  function updateProgress() {
    var fill = document.getElementById('progress-fill');
    var time = document.getElementById('time-label');
    if (!fill) return;
    var pct = audio.duration ? (audio.currentTime / audio.duration * 100) : 0;
    fill.style.width = pct + '%';
    if (time) time.textContent = fmt(audio.currentTime);
  }

  function fmt(s) {
    s = Math.floor(s || 0);
    return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
  }

  /* ── Panneau lecteur ─────────────────────────────────────────────────────── */
  function showPlayer(t) {
    var bar = document.getElementById('player-bar');
    bar.classList.add('show');
    document.getElementById('player-title').textContent    = t.title;
    document.getElementById('player-playlist').textContent = labelOf(t.playlist);
    document.getElementById('time-label').textContent      = '0:00';
    document.getElementById('progress-fill').style.width   = '0%';

    var imp = document.getElementById('import-btn');
    imp.textContent = 'Importer dans Premiere Pro';
    imp.disabled    = false;
  }

  /* ── Import dans Premiere ────────────────────────────────────────────────── */
  function importTrack() {
    var t = filtered[activeIdx];
    if (!t) return;
    var imp = document.getElementById('import-btn');
    imp.disabled    = true;
    imp.textContent = 'Téléchargement…';

    // Télécharge via Cloudinary (fl_attachment pour forcer le download)
    var dlUrl = t.url.replace('/upload/', '/upload/fl_attachment/');
    var ext   = t.url.split('.').pop().split('?')[0] || 'mp3';
    var safe  = t.title.replace(/[^a-zA-Z0-9_\- ]/g, '').trim();
    var fname = safe + '.' + ext;

    // Utilise l'XMLHttpRequest CEF pour récupérer les octets
    var xhr = new XMLHttpRequest();
    xhr.open('GET', dlUrl, true);
    xhr.responseType = 'arraybuffer';
    xhr.onload = function () {
      if (xhr.status !== 200) {
        imp.textContent = 'Erreur téléchargement (' + xhr.status + ')';
        imp.disabled = false;
        return;
      }
      // Ecrit le fichier via CSInterface / Node.js
      var bytes = new Uint8Array(xhr.response);
      var filePath = DOWNLOAD_DIR + '/' + fname;
      writeAndImport(bytes, filePath, t, imp);
    };
    xhr.onerror = function () {
      imp.textContent = 'Erreur réseau';
      imp.disabled = false;
    };
    xhr.send();
  }

  function writeAndImport(bytes, filePath, track, btn) {
    try {
      var cs = new CSInterface();
      // Encode en base64 pour passer via evalScript
      var b64 = btoa(String.fromCharCode.apply(null, bytes));
      var safeB64 = b64.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
      // Ecrit le fichier via ExtendScript (Folder.temp)
      var script =
        '(function(){\n' +
        '  var b64="' + safeB64 + '";\n' +
        '  var raw=Base64.decode(b64);\n' +
        '  var f=new File("' + filePath.replace(/\\/g, '/') + '");\n' +
        '  f.open("w");f.write(raw);f.close();\n' +
        '  return importAndInsertClip("' + filePath.replace(/\\/g, '/') + '");\n' +
        '})()';
      cs.evalScript(script, function (result) {
        var res = {};
        try { res = JSON.parse(result); } catch (e) {}
        if (res.error) {
          btn.textContent = 'Erreur : ' + res.error;
          btn.disabled = false;
        } else if (res.inserted) {
          btn.textContent = '✓ Inséré dans la séquence';
          logDownload(track);
        } else {
          btn.textContent = '✓ Importé dans le projet';
          logDownload(track);
        }
      });
    } catch (e) {
      btn.textContent = 'Erreur CEP';
      btn.disabled = false;
    }
  }

  function logDownload(track) {
    if (!sbSession) return;
    sbFetch('/rest/v1/downloads', {
      method: 'POST',
      body: JSON.stringify({
        user_id: sbSession.user.id,
        track_id: track.id,
        track_title: track.title,
        track_playlist: track.playlist,
        track_url: track.url
      })
    }).catch(function () {});
  }

  /* ── Auth Supabase ───────────────────────────────────────────────────────── */
  function showLogin() {
    document.getElementById('login-modal').classList.add('show');
    document.getElementById('login-email').value    = '';
    document.getElementById('login-password').value = '';
    document.getElementById('login-err').textContent = '';
  }

  function hideLogin() {
    document.getElementById('login-modal').classList.remove('show');
  }

  function doLogin() {
    var email = document.getElementById('login-email').value.trim();
    var pass  = document.getElementById('login-password').value;
    var err   = document.getElementById('login-err');
    var btn   = document.getElementById('login-btn');
    if (!email || !pass) { err.textContent = 'Email et mot de passe requis.'; return; }
    btn.disabled = true; btn.textContent = '…';

    sbFetch('/auth/v1/token?grant_type=password', {
      method: 'POST',
      body: JSON.stringify({ email: email, password: pass })
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error || !data.access_token) {
        err.textContent = data.error_description || data.error || 'Identifiants incorrects.';
        btn.disabled = false; btn.textContent = 'Connexion';
        return;
      }
      sbSession = data;
      hideLogin();
      updateAuthUI();
      // Pré-charge les crédits si un morceau est sélectionné
      if (activeIdx >= 0) preloadCredits([filtered[activeIdx].id]);
    })
    .catch(function () {
      err.textContent = 'Erreur réseau.';
      btn.disabled = false; btn.textContent = 'Connexion';
    });
  }

  function doLogout() {
    if (sbSession) {
      sbFetch('/auth/v1/logout', { method: 'POST' }).catch(function () {});
    }
    sbSession    = null;
    creditsCache = {};
    updateAuthUI();
  }

  function updateAuthUI() {
    var wrap = document.getElementById('auth-area');
    if (sbSession && sbSession.user) {
      wrap.innerHTML = '<span class="user-badge" id="user-badge" title="Se déconnecter">' +
        esc(sbSession.user.email.split('@')[0]) + ' ✕</span>';
      document.getElementById('user-badge').addEventListener('click', doLogout);
    } else {
      wrap.innerHTML = '<button class="btn-auth" id="btn-login">Connexion</button>';
      document.getElementById('btn-login').addEventListener('click', showLogin);
    }
  }

  function preloadCredits(ids) {
    if (!sbSession || !ids.length) return;
    sbFetch('/rest/v1/credits?select=track_id,parts&track_id=in.(' + ids.join(',') + ')')
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        rows.forEach(function (r) { creditsCache[r.track_id] = r.parts || []; });
      })
      .catch(function () {});
  }

  /* ── Utilitaires ─────────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function labelOf(pl) {
    if (!pl) return '';
    return pl.replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function showState(html) {
    document.getElementById('track-list').innerHTML = '<div class="state-msg">' + html + '</div>';
  }

  /* ── Init ────────────────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    // Cherche le dossier Temp via CSInterface si disponible
    try {
      var cs = new CSInterface();
      DOWNLOAD_DIR = cs.getSystemPath('userData') + '/OSM-Downloads';
      // Crée le dossier si absent via ExtendScript
      cs.evalScript('(function(){ var f=new Folder("' + DOWNLOAD_DIR.replace(/\\/g, '/') + '"); if(!f.exists)f.create(); return f.fsName; })()',
        function (p) { if (p && p !== 'undefined') DOWNLOAD_DIR = p; });
    } catch (e) {
      DOWNLOAD_DIR = '~/Desktop/OSM-Downloads';
    }

    // Barre de recherche
    document.getElementById('search-input').addEventListener('input', function (ev) {
      searchQuery = ev.target.value;
      applyFilters();
    });

    // Barre de progression cliquable
    var prog = document.getElementById('progress-bar');
    if (prog) {
      prog.addEventListener('click', function (ev) {
        if (!audio.duration) return;
        var rect = prog.getBoundingClientRect();
        audio.currentTime = (ev.clientX - rect.left) / rect.width * audio.duration;
      });
    }

    // Bouton play/pause du lecteur
    document.getElementById('ctrl-play').addEventListener('click', function () {
      if (audio.paused) { audio.play().catch(function () {}); }
      else { audio.pause(); }
      renderTracks();
    });

    // Bouton import
    document.getElementById('import-btn').addEventListener('click', importTrack);

    // Auth
    updateAuthUI();

    // Login modal
    document.getElementById('login-form').addEventListener('submit', function (ev) {
      ev.preventDefault(); doLogin();
    });
    document.getElementById('cancel-login').addEventListener('click', hideLogin);

    // Chargement catalogue
    loadCatalogue();
  });
})();
