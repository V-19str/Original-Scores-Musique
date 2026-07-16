-- Bloc 1 : tracking des ecoutes + titres ajoutes depuis l'admin.
--
-- Trois choses :
--   1. table `plays`, calquee sur `downloads` (une ligne par ecoute reelle) ;
--   2. table `nouveaux_titres`, fusionnee au catalogue.json au chargement du
--      site : lecture publique, ecriture reservee a l'admin ;
--   3. get_admin_data() etendue (ecoutes recentes + top titres + compteurs par
--      client) et nouvelle RPC get_client_activity() pour le detail d'un client.
--
-- A executer dans le dashboard Supabase (SQL Editor), comme la migration
-- get_admin_data_jwt.

-- ===================================================================
-- 1. Table des ecoutes
-- ===================================================================

create table if not exists public.plays (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users on delete cascade not null,
  track_id text not null,
  track_title text,
  track_playlist text,
  track_url text,
  played_at timestamptz default now()
);

alter table public.plays enable row level security;

-- Meme modele que downloads_own : un client ne voit et n'ecrit que ses lignes.
-- L'admin passe par get_admin_data(), qui est security definer.
drop policy if exists "plays_own" on public.plays;
create policy "plays_own" on public.plays for all using (auth.uid() = user_id);

-- `plays` grossit beaucoup plus vite que `downloads` (une ligne par titre
-- ecoute, pas par titre telecharge) : les index portent sur les deux seuls
-- acces qui existent, le flux recent et le detail d'un client.
create index if not exists plays_played_at_idx on public.plays (played_at desc);
create index if not exists plays_user_id_idx on public.plays (user_id, played_at desc);
create index if not exists plays_track_id_idx on public.plays (track_id);

-- Meme traitement pour downloads, qui n'avait aucun index en dehors de sa PK.
create index if not exists downloads_downloaded_at_idx on public.downloads (downloaded_at desc);
create index if not exists downloads_user_id_idx on public.downloads (user_id, downloaded_at desc);
create index if not exists downloads_track_id_idx on public.downloads (track_id);

-- ===================================================================
-- 2. Table des titres ajoutes depuis l'admin
-- ===================================================================

create table if not exists public.nouveaux_titres (
  id uuid default gen_random_uuid() primary key,
  track_id text unique not null,
  title text not null,
  playlist text not null,
  duration text,
  url text not null,
  tags text[] default '{}',
  created_at timestamptz default now()
);

alter table public.nouveaux_titres enable row level security;

-- Lecture publique : ces titres completent catalogue.json, qui est lui-meme
-- servi en clair a tout visiteur. Rien de sensible ici.
drop policy if exists "nouveaux_titres_read" on public.nouveaux_titres;
create policy "nouveaux_titres_read" on public.nouveaux_titres for select using (true);

-- Ecriture : meme barriere que get_admin_data(), l'email du JWT verifie par
-- PostgREST. Un JWT ne peut pas etre forge sans le secret du projet.
drop policy if exists "nouveaux_titres_admin_insert" on public.nouveaux_titres;
create policy "nouveaux_titres_admin_insert" on public.nouveaux_titres
  for insert to authenticated
  with check (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

drop policy if exists "nouveaux_titres_admin_update" on public.nouveaux_titres;
create policy "nouveaux_titres_admin_update" on public.nouveaux_titres
  for update to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

drop policy if exists "nouveaux_titres_admin_delete" on public.nouveaux_titres;
create policy "nouveaux_titres_admin_delete" on public.nouveaux_titres
  for delete to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

grant select on public.nouveaux_titres to anon, authenticated;
grant insert, update, delete on public.nouveaux_titres to authenticated;

create index if not exists nouveaux_titres_playlist_idx on public.nouveaux_titres (playlist);

-- ===================================================================
-- 3. get_admin_data() : ajoute les ecoutes, le top titres et les compteurs
-- ===================================================================

-- `profiles`, `favorites` et `downloads` gardent exactement la forme actuelle :
-- admin.html continue de fonctionner tel quel entre cette migration et le
-- bloc 3. Les nouvelles cles sont purement additives.
--
-- `plays` est plafonnee a 200 lignes : le dashboard n'affiche qu'un flux
-- recent, et rapatrier des milliers d'ecoutes dans le navigateur a chaque
-- ouverture de l'admin ne servirait a rien. Le detail complet d'un client
-- passe par get_client_activity(), appelee a la demande.

create or replace function public.get_admin_data()
returns json
language plpgsql
security definer
set search_path = public, auth
as $$
begin
  if coalesce(auth.jwt() ->> 'email', '') <> 'vladimirstreiff@gmail.com' then
    raise exception 'Accès refusé';
  end if;

  return (
    select json_build_object(
      'profiles', (
        select coalesce(json_agg(
          json_build_object(
            'id', p.id, 'email', p.email,
            'prenom', p.prenom, 'nom', p.nom,
            'societe', p.societe, 'metier', p.metier,
            'created_at', p.created_at,
            'last_sign_in', u.last_sign_in_at,
            'nb_favorites', (select count(*) from favorites f where f.user_id = p.id),
            'nb_downloads', (select count(*) from downloads d where d.user_id = p.id),
            'nb_plays', (select count(*) from plays pl where pl.user_id = p.id),
            'last_activity', greatest(
              (select max(d.downloaded_at) from downloads d where d.user_id = p.id),
              (select max(pl.played_at) from plays pl where pl.user_id = p.id)
            )
          ) order by p.created_at desc
        ), '[]'::json)
        from profiles p left join auth.users u on u.id = p.id
      ),
      'favorites', (
        select coalesce(json_agg(row_to_json(f.*) order by f.created_at desc), '[]'::json)
        from favorites f
      ),
      'downloads', (
        select coalesce(json_agg(row_to_json(d.*) order by d.downloaded_at desc), '[]'::json)
        from downloads d
      ),
      'plays', (
        select coalesce(json_agg(row_to_json(t.*)), '[]'::json)
        from (
          select * from plays order by played_at desc limit 200
        ) t
      ),
      'top_tracks', (
        select coalesce(json_agg(row_to_json(t.*)), '[]'::json)
        from (
          select
            a.track_id,
            max(a.track_title) as track_title,
            max(a.track_playlist) as track_playlist,
            count(*) filter (where a.kind = 'play') as nb_plays,
            count(*) filter (where a.kind = 'download') as nb_downloads,
            max(a.at) as last_at
          from (
            select track_id, track_title, track_playlist, 'play'::text as kind, played_at as at
            from plays
            union all
            select track_id, track_title, track_playlist, 'download'::text as kind, downloaded_at as at
            from downloads
          ) a
          group by a.track_id
          order by count(*) desc, max(a.at) desc
          limit 30
        ) t
      )
    )
  );
end;
$$;

revoke all on function public.get_admin_data() from public, anon;
grant execute on function public.get_admin_data() to authenticated;

-- ===================================================================
-- 4. get_client_activity() : detail complet d'un seul client
-- ===================================================================

-- Appelee quand l'admin deplie une fiche client, pour ne pas charger l'activite
-- de tout le monde a l'ouverture du dashboard.

create or replace function public.get_client_activity(client_id uuid)
returns json
language plpgsql
security definer
set search_path = public, auth
as $$
begin
  if coalesce(auth.jwt() ->> 'email', '') <> 'vladimirstreiff@gmail.com' then
    raise exception 'Accès refusé';
  end if;

  return (
    select json_build_object(
      'favorites', (
        select coalesce(json_agg(row_to_json(f.*) order by f.created_at desc), '[]'::json)
        from favorites f where f.user_id = client_id
      ),
      'downloads', (
        select coalesce(json_agg(row_to_json(d.*) order by d.downloaded_at desc), '[]'::json)
        from downloads d where d.user_id = client_id
      ),
      'plays', (
        select coalesce(json_agg(row_to_json(t.*)), '[]'::json)
        from (
          select * from plays
          where user_id = client_id
          order by played_at desc
          limit 500
        ) t
      )
    )
  );
end;
$$;

revoke all on function public.get_client_activity(uuid) from public, anon;
grant execute on function public.get_client_activity(uuid) to authenticated;
