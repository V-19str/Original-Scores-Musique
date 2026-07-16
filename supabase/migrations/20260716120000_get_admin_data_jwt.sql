-- get_admin_data : remplace le controle par mot de passe par un controle sur
-- l'email du JWT.
--
-- Avant : get_admin_data(admin_pwd text) etait `security definer` (contourne
-- la RLS), n'etait protegee que par la comparaison admin_pwd = 'OSM_ADMIN_2026',
-- et etait `grant execute ... to anon`. Ce mot de passe etant en clair dans le
-- JavaScript d'admin.html sur un site public, n'importe qui pouvait appeler la
-- RPC et recuperer tous les profils clients (email, nom, societe, metier).
--
-- Apres : la fonction ne prend plus d'argument et lit l'email directement dans
-- le JWT verifie par PostgREST. Un appelant anonyme n'a pas de claim `email`
-- et est refuse ; un JWT ne peut pas etre forge sans le secret du projet.
--
-- Meme modele que l'Edge Function inviter-client, qui valide deja l'appelant.

-- 1. Nouvelle version, sans argument.
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
      )
    )
  );
end;
$$;

-- 2. Seuls les utilisateurs connectes peuvent l'appeler. Le controle sur
--    l'email reste la vraie barriere ; retirer `anon` est une precaution
--    supplementaire, pour qu'un appel non authentifie soit rejete avant meme
--    d'entrer dans la fonction.
revoke all on function public.get_admin_data() from public, anon;
grant execute on function public.get_admin_data() to authenticated;

-- 3. Supprime l'ancienne version protegee par mot de passe. C'est CETTE ligne
--    qui ferme la faille : tant qu'elle existe, le mot de passe publie dans
--    l'historique git reste utilisable.
drop function if exists public.get_admin_data(text);
