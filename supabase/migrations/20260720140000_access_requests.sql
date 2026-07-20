-- Bloc SUPERVISION : demandes d'accès (inscriptions) tracées en base.
--
-- inscription.html écrit chaque demande dans `access_requests` (en plus de
-- l'email Formspree existant). L'admin voit qui a demandé un accès, quand, et
-- avec quel statut. Un Database Webhook Supabase sur l'INSERT de cette table
-- déclenche l'Edge Function `notifier-admin` (email Brevo à l'administrateur).
--
-- À exécuter dans le dashboard Supabase (SQL Editor), après les migrations
-- précédentes.

create table if not exists public.access_requests (
  id uuid default gen_random_uuid() primary key,
  email text not null,
  prenom text,
  nom text,
  telephone text,
  societe text,
  metier text,
  projet text,
  message text,
  -- pending (nouvelle) -> invited (admin a envoyé l'invitation).
  -- Le statut « actif » est déduit côté admin en croisant l'email avec profiles.
  status text not null default 'pending',
  created_at timestamptz default now()
);

alter table public.access_requests enable row level security;

-- Insertion publique : le formulaire d'inscription est ouvert à tout visiteur.
-- On ne veut PAS que ces lignes soient lisibles par autrui : seul l'admin lit.
drop policy if exists "access_requests_public_insert" on public.access_requests;
create policy "access_requests_public_insert" on public.access_requests
  for insert to anon, authenticated
  with check (true);

drop policy if exists "access_requests_admin_select" on public.access_requests;
create policy "access_requests_admin_select" on public.access_requests
  for select to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

drop policy if exists "access_requests_admin_update" on public.access_requests;
create policy "access_requests_admin_update" on public.access_requests
  for update to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

drop policy if exists "access_requests_admin_delete" on public.access_requests;
create policy "access_requests_admin_delete" on public.access_requests
  for delete to authenticated
  using (coalesce(auth.jwt() ->> 'email', '') = 'vladimirstreiff@gmail.com');

grant insert on public.access_requests to anon, authenticated;
grant select, update, delete on public.access_requests to authenticated;

create index if not exists access_requests_created_at_idx on public.access_requests (created_at desc);
create index if not exists access_requests_email_idx on public.access_requests (lower(email));
