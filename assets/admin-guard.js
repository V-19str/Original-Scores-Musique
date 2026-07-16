/*
 * admin-guard.js — reserve une page a l'administrateur.
 *
 * Meme mecanisme que le panneau d'approbation (admin.html) : connexion
 * Supabase par email/mot de passe, puis controle que l'email correspond a
 * ADMIN_EMAIL. La session est partagee avec admin.html (meme domaine, meme
 * stockage) : se connecter sur l'une ouvre les autres.
 *
 * ⚠ PORTEE REELLE — a ne pas confondre avec une protection serveur.
 * Le site est statique : ce fichier et le HTML qu'il masque sont
 * telechargeables par n'importe qui (curl, view-source, cache). Ce garde
 * empeche l'usage occasionnel de l'outil dans un navigateur, il ne rend pas
 * son contenu secret. Toute donnee sensible doit etre protegee cote serveur
 * (RLS Supabase), jamais par cet ecran.
 *
 * Usage — dans <head>, AVANT tout rendu :
 *   <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>
 *   <script src="assets/admin-guard.js"></script>
 */
(function () {
  var SUPABASE_URL = 'https://ubpmzncfhkohoyfonjbb.supabase.co';
  var SUPABASE_KEY = 'sb_publishable_8rWkPwFktGZLsk79WCq7PQ_3Gb1xykh';
  var ADMIN_EMAIL  = 'vladimirstreiff@gmail.com';

  // Masque la page des le parsing : evite que le contenu clignote avant la
  // verification de session, qui est asynchrone.
  var hide = document.createElement('style');
  hide.id = 'admin-guard-hide';
  hide.textContent = 'body > *:not(#admin-guard){visibility:hidden !important}';
  document.head.appendChild(hide);

  var sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

  function reveal() {
    var s = document.getElementById('admin-guard-hide');
    if (s) s.remove();
    var g = document.getElementById('admin-guard');
    if (g) g.remove();
  }

  function buildGate() {
    var g = document.createElement('div');
    g.id = 'admin-guard';
    g.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#0a0a0a;color:#fff;' +
      'display:flex;align-items:center;justify-content:center;flex-direction:column;gap:28px;' +
      "font-family:'Montserrat',system-ui,sans-serif";
    g.innerHTML =
      '<div style="display:flex;align-items:center;gap:12px">' +
        '<div style="background:#E50914;color:#fff;font-size:13px;font-weight:700;letter-spacing:2px;padding:6px 10px;border-radius:3px">OSM</div>' +
        '<div style="font-size:15px;font-weight:600;letter-spacing:3px">ORIGINAL SCORES MUSIC</div>' +
      '</div>' +
      '<div style="background:#1f1f1f;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:40px;width:360px;max-width:90vw;text-align:center">' +
        '<div style="font-size:13px;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px">Connexion Admin</div>' +
        '<div style="font-size:12px;color:#888;margin-bottom:24px">Réservé à Vladimir Streiff</div>' +
        '<input id="ag-email" type="email" autocomplete="email" placeholder="vladimirstreiff@gmail.com" ' +
          'style="width:100%;background:#2a2a2a;border:1px solid rgba(255,255,255,0.1);border-radius:4px;padding:11px 14px;color:#fff;font-size:13px;margin-bottom:12px;outline:none;font-family:inherit">' +
        '<input id="ag-pw" type="password" autocomplete="current-password" placeholder="••••••••" ' +
          'style="width:100%;background:#2a2a2a;border:1px solid rgba(255,255,255,0.1);border-radius:4px;padding:11px 14px;color:#fff;font-size:13px;margin-bottom:16px;outline:none;font-family:inherit">' +
        '<button id="ag-btn" style="width:100%;background:#E50914;color:#fff;border:none;padding:12px;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;border-radius:4px;cursor:pointer;font-family:inherit">Se connecter</button>' +
        '<div id="ag-err" style="font-size:11px;color:#E50914;margin-top:12px;display:none"></div>' +
        '<div style="font-size:11px;color:#666;margin-top:16px"><a href="index.html" style="color:#888;text-decoration:none">← Retour au catalogue</a></div>' +
      '</div>';
    document.body.appendChild(g);

    var err = g.querySelector('#ag-err');
    var btn = g.querySelector('#ag-btn');

    function fail(msg) { err.textContent = msg; err.style.display = 'block'; }

    async function submit() {
      var email = g.querySelector('#ag-email').value.trim();
      var pw = g.querySelector('#ag-pw').value;
      err.style.display = 'none';
      if (!email || !pw) { fail('Remplissez email et mot de passe.'); return; }

      btn.disabled = true; btn.textContent = 'Connexion...';
      var res = await sb.auth.signInWithPassword({ email: email, password: pw });
      btn.disabled = false; btn.textContent = 'Se connecter';

      if (res.error) {
        fail(res.error.message.indexOf('Invalid') !== -1 ? 'Email ou mot de passe incorrect.' : res.error.message);
        return;
      }
      if (res.data.user.email !== ADMIN_EMAIL) {
        fail("Accès refusé. Ce compte n'est pas autorisé.");
        await sb.auth.signOut();
        return;
      }
      reveal();
    }

    btn.addEventListener('click', submit);
    g.querySelector('#ag-pw').addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    g.querySelector('#ag-email').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') g.querySelector('#ag-pw').focus();
    });
  }

  async function init() {
    var res = await sb.auth.getSession();
    var session = res.data.session;
    if (session && session.user && session.user.email === ADMIN_EMAIL) {
      reveal();          // deja connecte sur admin.html : on ouvre directement
    } else {
      buildGate();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
