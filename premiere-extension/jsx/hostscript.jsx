/**
 * hostscript.jsx — ExtendScript côté Premiere Pro.
 * Importe un fichier audio dans le projet actif et l'insère
 * dans la séquence active à la position de la tête de lecture.
 */

function importAndInsertClip(filePath) {
  try {
    var proj = app.project;
    if (!proj) return JSON.stringify({ error: 'Aucun projet ouvert.' });

    var imported = proj.importFiles([filePath], true, proj.rootItem, false);
    if (!imported || !proj.rootItem.children.numItems) {
      return JSON.stringify({ error: 'Échec import : ' + filePath });
    }

    // Cherche le clip importé dans les items racine
    var clip = null;
    for (var i = 0; i < proj.rootItem.children.numItems; i++) {
      var item = proj.rootItem.children[i];
      if (item.getMediaPath && item.getMediaPath() === filePath) {
        clip = item;
        break;
      }
    }
    if (!clip) {
      // fallback : dernier item importé
      clip = proj.rootItem.children[proj.rootItem.children.numItems - 1];
    }

    var seq = proj.activeSequence;
    if (!seq) {
      return JSON.stringify({ ok: true, inserted: false, msg: 'Clip importé. Ouvrez une séquence pour l\'insérer.' });
    }

    var inPoint = seq.getPlayerPosition();
    seq.audioTracks[0].insertClip(clip, inPoint.seconds);

    return JSON.stringify({ ok: true, inserted: true });
  } catch (e) {
    return JSON.stringify({ error: String(e) });
  }
}

function getProjectName() {
  try {
    return app.project ? app.project.name : '';
  } catch (e) { return ''; }
}
