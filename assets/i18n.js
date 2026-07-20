/*
 * i18n.js — moteur de traduction FR/EN partagé par tout le site OSM.
 *
 * FR est la langue par défaut et la langue « source » : les pages sont écrites
 * en français. La traduction anglaise se fait par CORRESPONDANCE DE PHRASES :
 * chaque page fournit une carte français → anglais avant de charger ce script :
 *
 *   <script>window.OSM_I18N_MAP = Object.assign(window.OSM_I18N_MAP||{}, {
 *     "Accueil": "Home",
 *     "Rechercher une musique, une ambiance, un instrument...": "Search a track, a mood, an instrument...",
 *     ...
 *   });</script>
 *   <script src="assets/i18n.js"></script>
 *
 * Le moteur parcourt les nœuds texte et les attributs placeholder / title /
 * aria-label ; quand le texte français correspond exactement (aux espaces près)
 * à une clé de la carte, il est remplacé par l'anglais. Passer en FR restaure
 * les textes d'origine. Les contenus non présents dans la carte (noms de
 * playlists, tags du catalogue, titres de morceaux…) restent donc en français.
 *
 * Le choix est mémorisé dans localStorage (osm-lang) et partagé entre les pages.
 * Le sélecteur de langue s'auto-construit dans <span data-osm-langpicker></span>.
 * Un MutationObserver traduit les contenus injectés dynamiquement lorsqu'on est
 * en anglais. Pour un texte généré en JS, window.osmT('phrase FR') renvoie la
 * traduction courante.
 */
(function () {
  var MAP = {};                 // clé française normalisée -> anglais
  var cache = [];               // sauvegardes pour restaurer le français
  var observer = null;

  function normLang(l) { return l === 'en' ? 'en' : 'fr'; }
  function getLang() { return normLang(localStorage.getItem('osm-lang') || 'fr'); }
  function norm(s) { return String(s).replace(/\s+/g, ' ').trim(); }

  function buildMap() {
    var raw = window.OSM_I18N_MAP || {};
    MAP = {};
    for (var k in raw) if (Object.prototype.hasOwnProperty.call(raw, k)) MAP[norm(k)] = raw[k];
  }

  var SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1 };

  function translateTextNodes(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var parent = node.parentNode;
      if (!parent || SKIP[parent.nodeName]) return;
      var raw = node.nodeValue;
      if (!raw) return;
      var key = norm(raw);
      if (!key) return;
      var en = MAP[key];
      if (en == null) return;
      var lead = (raw.match(/^\s*/) || [''])[0];
      var trail = (raw.match(/\s*$/) || [''])[0];
      cache.push({ node: node, orig: raw });
      node.nodeValue = lead + en + trail;
    });
  }

  function translateAttrs(root) {
    var attrs = ['placeholder', 'title', 'aria-label'];
    var els = root.querySelectorAll('[placeholder],[title],[aria-label]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      for (var a = 0; a < attrs.length; a++) {
        if (!el.hasAttribute(attrs[a])) continue;
        var raw = el.getAttribute(attrs[a]);
        var en = MAP[norm(raw)];
        if (en == null) continue;
        cache.push({ el: el, attr: attrs[a], orig: raw });
        el.setAttribute(attrs[a], en);
      }
    }
  }

  function translate(root) { translateTextNodes(root); translateAttrs(root); }

  function restore() {
    for (var i = 0; i < cache.length; i++) {
      var c = cache[i];
      if (c.node) { if (c.node.parentNode) c.node.nodeValue = c.orig; }
      else if (c.el) c.el.setAttribute(c.attr, c.orig);
    }
    cache = [];
  }

  function apply(lang) {
    document.documentElement.setAttribute('lang', lang);
    restore();
    if (lang === 'en') translate(document.body);

    var opts = document.querySelectorAll('.lang-opt');
    for (var i = 0; i < opts.length; i++) opts[i].classList.toggle('active', opts[i].getAttribute('data-lang') === lang);
    var cur = document.getElementById('lang-current');
    if (cur) cur.textContent = lang.toUpperCase();

    window.OSM_LANG = lang;
    document.dispatchEvent(new CustomEvent('osm-lang-change', { detail: { lang: lang } }));
  }

  // ── Sélecteur de langue (auto-construit dans data-osm-langpicker) ──
  function injectStyle() {
    if (document.getElementById('osm-lang-style')) return;
    var s = document.createElement('style');
    s.id = 'osm-lang-style';
    s.textContent =
      '.lang-picker{position:relative;display:inline-block}' +
      '.lang-menu{position:absolute;top:calc(100% + 6px);right:0;background:var(--bg-deep,#111);border:1px solid var(--border,rgba(255,255,255,.12));border-radius:8px;padding:6px;display:none;flex-direction:column;gap:2px;z-index:400;min-width:150px;box-shadow:0 10px 28px rgba(0,0,0,.28)}' +
      '.lang-menu.open{display:flex}' +
      ".lang-opt{display:flex;align-items:center;gap:8px;background:none;border:none;color:var(--text2,#ccc);padding:8px 10px;border-radius:5px;font-family:'Montserrat',sans-serif;font-size:12px;cursor:pointer;text-align:left;transition:background .15s,color .15s;white-space:nowrap}" +
      '.lang-opt:hover{background:var(--bg3,#2a2a2a);color:var(--text,#fff)}' +
      '.lang-opt.active{color:var(--text,#fff);font-weight:600;background:var(--bg2,#1f1f1f)}';
    document.head.appendChild(s);
  }

  function buildPickers() {
    var slots = document.querySelectorAll('[data-osm-langpicker]');
    for (var i = 0; i < slots.length; i++) {
      var slot = slots[i];
      if (slot.getAttribute('data-osm-built')) continue;
      slot.setAttribute('data-osm-built', '1');
      slot.className = (slot.className ? slot.className + ' ' : '') + 'lang-picker';
      slot.innerHTML =
        '<button class="btn-nav" type="button" onclick="osmToggleLangMenu(event)" title="Langue / Language" aria-haspopup="true">🌐 <span id="lang-current">FR</span> ▾</button>' +
        '<div class="lang-menu" id="lang-menu">' +
        '<button class="lang-opt" data-lang="fr" type="button" onclick="osmSetLang(\'fr\')">🇫🇷 Français</button>' +
        '<button class="lang-opt" data-lang="en" type="button" onclick="osmSetLang(\'en\')">🇬🇧 English</button>' +
        '</div>';
    }
  }

  window.osmToggleLangMenu = function (e) {
    if (e) e.stopPropagation();
    var m = document.getElementById('lang-menu');
    if (m) m.classList.toggle('open');
  };
  window.osmSetLang = function (l) {
    l = normLang(l);
    localStorage.setItem('osm-lang', l);
    var m = document.getElementById('lang-menu');
    if (m) m.classList.remove('open');
    apply(l);
  };
  window.osmT = function (phrase) {
    if (getLang() !== 'en') return phrase;
    var en = MAP[norm(phrase)];
    return en != null ? en : phrase;
  };
  window.osmLang = getLang;

  document.addEventListener('click', function (e) {
    var p = e.target.closest ? e.target.closest('.lang-picker') : null;
    if (!p) { var m = document.getElementById('lang-menu'); if (m) m.classList.remove('open'); }
  });

  // Traduit les contenus ajoutés dynamiquement quand on est en anglais.
  function startObserver() {
    if (observer || typeof MutationObserver === 'undefined') return;
    observer = new MutationObserver(function (muts) {
      if (getLang() !== 'en') return;
      muts.forEach(function (m) {
        for (var i = 0; i < m.addedNodes.length; i++) {
          var node = m.addedNodes[i];
          if (node.nodeType === 1) translate(node);
          else if (node.nodeType === 3 && node.parentNode && !SKIP[node.parentNode.nodeName]) {
            var key = norm(node.nodeValue), en = key && MAP[key];
            if (en != null) {
              var raw = node.nodeValue;
              cache.push({ node: node, orig: raw });
              node.nodeValue = (raw.match(/^\s*/) || [''])[0] + en + (raw.match(/\s*$/) || [''])[0];
            }
          }
        }
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    buildMap();
    injectStyle();
    buildPickers();
    apply(getLang());
    startObserver();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
