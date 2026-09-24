-- get_admin_data : ajoute un mode d'accès par mot de passe statique en plus
-- du contrôle par JWT. Permet à admin.html de fonctionner sans session Supabase.
--
-- Deux modes acceptés :
--   1. JWT avec email vladimirstreiff@gmail.com (ancien comportement)
--   2. admin_pwd = 'OSM_ADMIN_2026' (nouveau, pour accès direct sans login)

create or replace function public.get_admin_data(admin_pwd text default '')
returns json
language plpgsql
security definer
set search_path = public, auth
as $$
begin
  if admin_pwd <> 'OSM_ADMIN_2026'
     and coalesce(auth.jwt() ->> 'email', '') <> 'vladimirstreiff@gmail.com' then
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
            'nb_favorites', coalesce(
              (select count(*) from favorites f where f.user_id = p.id), 0),
            'nb_downloads', coalesce(
              (select count(*) from downloads d where d.user_id = p.id), 0),
            'nb_plays', coalesce(
              (select count(*) from plays pl where pl.user_id = p.id), 0),
            'last_activity', (
              select greatest(
                max(d.downloaded_at),
                max(pl.played_at)
              )
              from downloads d, plays pl
              where d.user_id = p.id and pl.user_id = p.id
            ),
            'last_sign_in', u.last_sign_in_at
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
        select coalesce(json_agg(row_to_json(pl.*) order by pl.played_at desc limit 200), '[]'::json)
        from plays pl
      ),
      'top_tracks', (
        select coalesce(json_agg(t order by t.nb_plays desc), '[]'::json)
        from (
          select track_id, track_title, track_playlist,
                 count(*) filter (where kind = 'play') as nb_plays,
                 count(*) filter (where kind = 'dl') as nb_downloads
          from (
            select track_id, track_title, track_playlist, 'play' as kind from plays
            union all
            select track_id, track_title, track_playlist, 'dl' as kind from downloads
          ) all_events
          group by track_id, track_title, track_playlist
          order by nb_plays desc
          limit 20
        ) t
      )
    )
  );
end;
$$;

-- Accessible sans auth (l'admin_pwd protège l'accès)
grant execute on function public.get_admin_data(text) to anon, authenticated;
