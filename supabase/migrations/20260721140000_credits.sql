-- Bloc CUE SHEET : compositeurs et clés de répartition, réservés aux monteurs.
--
-- Le générateur de cue sheet SACEM (« Easy Cue Sheet », côté client) a besoin
-- du compositeur et de sa clé pour chaque titre. Cette donnée vient de
-- CAT_PARTS dans admin-sacem.html, extraite par build_credits.py.
--
-- Elle n'est PAS publiée dans le dépôt : la table ci-dessous est lisible par
-- les seuls comptes authentifiés (monteurs approuvés sur invitation), jamais
-- par anon. C'est la raison d'être de la policy `credits_authenticated_select`.
--
-- À exécuter dans le dashboard Supabase (SQL Editor), puis charger les lignes
-- avec le fichier credits_seed.sql produit par build_credits.py.

create table if not exists public.credits (
  -- id du morceau dans catalogue.json (= public_id Cloudinary)
  track_id text primary key,
  -- [{"nom": "Streiff Vladimir", "cle": 33.33}, ...] — somme des clés = 100
  parts jsonb not null,
  updated_at timestamptz default now()
);

alter table public.credits enable row level security;

-- Lecture réservée aux comptes connectés. Les visiteurs anonymes n'ont aucun
-- accès : les clés de répartition ne doivent pas être aspirables publiquement.
drop policy if exists "credits_authenticated_select" on public.credits;
create policy "credits_authenticated_select" on public.credits
  for select to authenticated
  using (true);

-- Écriture réservée à l'administrateur, même convention que les autres tables.
drop policy if exists "credits_admin_write" on public.credits;
create policy "credits_admin_write" on public.credits
  for all to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com')
  with check (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');
