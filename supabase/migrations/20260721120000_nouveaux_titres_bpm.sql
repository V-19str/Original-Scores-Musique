-- Bloc AJOUT DE MORCEAUX : colonne bpm sur nouveaux_titres.
--
-- index.html lit déjà `n.bpm` en fusionnant nouveaux_titres au catalogue, et les
-- filtres pro (BPM / énergie) s'appuient dessus : sans cette colonne, un titre
-- ajouté depuis l'admin sort de tous les filtres BPM. catalogue.json stocke le
-- BPM en entier, on garde le même type.
--
-- À exécuter dans le dashboard Supabase (SQL Editor), après la migration
-- plays_et_nouveaux_titres.

alter table public.nouveaux_titres
  add column if not exists bpm integer;
