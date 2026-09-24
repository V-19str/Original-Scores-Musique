CREATE OR REPLACE FUNCTION public.get_admin_data(admin_pwd text DEFAULT NULL)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
BEGIN
  IF coalesce(admin_pwd, '') <> 'OSM_ADMIN_2026'
     AND coalesce(auth.jwt() ->> 'email', '') <> 'vladimirstreiff@gmail.com'
  THEN
    RAISE EXCEPTION 'Acces refuse';
  END IF;

  RETURN (
    SELECT json_build_object(
      'profiles', (
        SELECT coalesce(json_agg(
          json_build_object(
            'id', p.id,
            'email', p.email,
            'prenom', p.prenom,
            'nom', p.nom,
            'societe', p.societe,
            'metier', p.metier,
            'created_at', p.created_at,
            'nb_favorites', coalesce((SELECT count(*) FROM favorites f WHERE f.user_id = p.id), 0),
            'nb_downloads', coalesce((SELECT count(*) FROM downloads d WHERE d.user_id = p.id), 0),
            'nb_plays', coalesce((SELECT count(*) FROM plays pl WHERE pl.user_id = p.id), 0),
            'last_sign_in', u.last_sign_in_at
          ) ORDER BY p.created_at DESC
        ), '[]'::json)
        FROM profiles p
        LEFT JOIN auth.users u ON u.id = p.id
      ),
      'favorites', (
        SELECT coalesce(json_agg(row_to_json(f.*) ORDER BY f.created_at DESC), '[]'::json)
        FROM favorites f
      ),
      'downloads', (
        SELECT coalesce(json_agg(row_to_json(d.*) ORDER BY d.downloaded_at DESC), '[]'::json)
        FROM downloads d
      ),
      'plays', (
        SELECT coalesce(json_agg(row_to_json(pl.*)), '[]'::json)
        FROM (SELECT * FROM plays ORDER BY played_at DESC LIMIT 200) pl
      ),
      'top_tracks', (
        SELECT coalesce(json_agg(t ORDER BY t.nb_plays DESC), '[]'::json)
        FROM (
          SELECT
            track_id, track_title, track_playlist,
            count(*) FILTER (WHERE kind = 'play') AS nb_plays,
            count(*) FILTER (WHERE kind = 'dl')   AS nb_downloads
          FROM (
            SELECT track_id, track_title, track_playlist, 'play' AS kind FROM plays
            UNION ALL
            SELECT track_id, track_title, track_playlist, 'dl'   AS kind FROM downloads
          ) e
          GROUP BY track_id, track_title, track_playlist
          ORDER BY nb_plays DESC
          LIMIT 20
        ) t
      )
    )
  );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_admin_data(text) TO anon, authenticated;
