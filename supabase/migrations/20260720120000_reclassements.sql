-- Bloc RECLASSEMENT : déplacer un titre d'une playlist à une autre sans toucher
-- catalogue.json.
--
-- Deux tables, sur le même modèle que nouveaux_titres :
--   1. `reclassements`         : l'override de playlist d'un titre, fusionné au
--      catalogue au chargement du site (lecture publique, écriture admin).
--   2. `reclassements_refuses` : les suggestions écartées par l'admin, pour ne
--      plus les reproposer (lecture + écriture admin uniquement).
--
-- À exécuter dans le dashboard Supabase (SQL Editor), après les migrations
-- get_admin_data_jwt et plays_et_nouveaux_titres.

-- ===================================================================
-- 1. reclassements : override de playlist, fusionné au catalogue public
-- ===================================================================

create table if not exists public.reclassements (
  track_id text primary key,
  track_title text,
  from_playlist text,
  to_playlist text not null,
  created_at timestamptz default now()
);

alter table public.reclassements enable row level security;

-- Lecture publique : ces overrides complètent catalogue.json, servi en clair à
-- tout visiteur. Rien de sensible.
drop policy if exists "reclassements_read" on public.reclassements;
create policy "reclassements_read" on public.reclassements for select using (true);

-- Écriture : même barrière que nouveaux_titres — l'email du JWT vérifié par
-- PostgREST. Un JWT ne peut pas être forgé sans le secret du projet.
drop policy if exists "reclassements_admin_insert" on public.reclassements;
create policy "reclassements_admin_insert" on public.reclassements
  for insert to authenticated
  with check (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

drop policy if exists "reclassements_admin_update" on public.reclassements;
create policy "reclassements_admin_update" on public.reclassements
  for update to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

drop policy if exists "reclassements_admin_delete" on public.reclassements;
create policy "reclassements_admin_delete" on public.reclassements
  for delete to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

grant select on public.reclassements to anon, authenticated;
grant insert, update, delete on public.reclassements to authenticated;

-- ===================================================================
-- 2. reclassements_refuses : suggestions écartées (admin seulement)
-- ===================================================================

create table if not exists public.reclassements_refuses (
  track_id text not null,
  to_playlist text not null,
  created_at timestamptz default now(),
  primary key (track_id, to_playlist)
);

alter table public.reclassements_refuses enable row level security;

-- Rien de public ici : c'est un outil d'aide à la décision réservé à l'admin.
drop policy if exists "reclassements_refuses_admin_all" on public.reclassements_refuses;
create policy "reclassements_refuses_admin_all" on public.reclassements_refuses
  for all to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com')
  with check (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

grant select, insert, delete on public.reclassements_refuses to authenticated;
