-- Bloc SACEM CONFIDENTIEL : revenus, previsionnel et co-auteurs, reserves a
-- l'administrateur.
--
-- admin-sacem.html embarquait en dur, dans son JavaScript servi publiquement,
-- les revenus SACEM reels (par annee, chaine, type), le previsionnel de
-- versements, et le detail des co-auteurs (noms + revenus de tiers). Le garde
-- admin-guard.js est purement cote client : le HTML restait telechargeable par
-- curl ou view-source. Ces donnees sortent donc du fichier et vivent ici,
-- lisibles par le seul administrateur.
--
-- Modele identique a la table `credits`, mais la lecture est reservee a
-- l'admin (et non a tous les authenticated) : ces chiffres ne concernent que
-- lui et des tiers, aucun monteur ne doit y acceder.
--
-- Chaque bloc du dashboard (REVENUS_ANNEE, CAT_RICH, PROGS_DETAIL...) est une
-- ligne : key = nom du bloc, payload = le JSON tel quel. admin-sacem.html lit
-- la table apres connexion et rehydrate ses variables.
--
-- A executer dans le dashboard Supabase (SQL Editor), puis charger les lignes
-- avec sacem_data_seed.sql (produit par build_sacem_data.py, hors depot).

create table if not exists public.sacem_data (
  key text primary key,
  payload jsonb not null,
  updated_at timestamptz default now()
);

alter table public.sacem_data enable row level security;

-- Lecture ET ecriture reservees a l'administrateur. Contrairement a `credits`,
-- meme un compte connecte (monteur) n'a aucun acces : ces donnees sont
-- strictement personnelles.
drop policy if exists "sacem_data_admin_all" on public.sacem_data;
create policy "sacem_data_admin_all" on public.sacem_data
  for all to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com')
  with check (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

-- Aucun acces anonyme : la cle publiable du site ne doit rien pouvoir lire.
revoke all on public.sacem_data from anon;
