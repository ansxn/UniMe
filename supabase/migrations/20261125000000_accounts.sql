-- UniMe accounts: profiles + per-user saved quiz results, ChanceMe checks and programs.
-- Every table has RLS so a user can only read and write their own rows.
-- Policies use `(select auth.uid())` so Postgres evaluates it once per query.

-- ---------------------------------------------------------------------------
-- profiles: one row per auth user, created by a trigger on signup
-- ---------------------------------------------------------------------------
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 80),
  grad_year smallint check (grad_year between 2000 and 2100),
  created_at timestamptz not null default now()
);

comment on table public.profiles is 'Public profile basics for each UniMe user (id = auth.users.id).';

alter table public.profiles enable row level security;

create policy "Users can view their own profile"
  on public.profiles for select to authenticated
  using ((select auth.uid()) = id);

create policy "Users can create their own profile"
  on public.profiles for insert to authenticated
  with check ((select auth.uid()) = id);

create policy "Users can update their own profile"
  on public.profiles for update to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

create policy "Users can delete their own profile"
  on public.profiles for delete to authenticated
  using ((select auth.uid()) = id);

-- Create the profile row when someone signs up. The app passes the name as
-- signUp({ options: { data: { display_name } } }).
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    nullif(left(btrim(new.raw_user_meta_data ->> 'display_name'), 80), '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

-- Only the trigger should run this.
revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- quiz_results: each MatchMe attempt (answers sent to /api/match + its response)
-- ---------------------------------------------------------------------------
create table public.quiz_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  answers jsonb not null,
  matches jsonb not null,
  created_at timestamptz not null default now()
);

create index quiz_results_user_id_created_at_idx
  on public.quiz_results (user_id, created_at desc);

alter table public.quiz_results enable row level security;

create policy "Users can view their own quiz results"
  on public.quiz_results for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can save their own quiz results"
  on public.quiz_results for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Users can update their own quiz results"
  on public.quiz_results for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "Users can delete their own quiz results"
  on public.quiz_results for delete to authenticated
  using ((select auth.uid()) = user_id);

-- ---------------------------------------------------------------------------
-- chance_checks: each ChanceMe check (form inputs + /api/chance-me prediction)
-- ---------------------------------------------------------------------------
create table public.chance_checks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  inputs jsonb not null,      -- {school, program, top6, ecs}
  prediction jsonb not null,  -- the `prediction` object returned by /api/chance-me
  created_at timestamptz not null default now()
);

create index chance_checks_user_id_created_at_idx
  on public.chance_checks (user_id, created_at desc);

alter table public.chance_checks enable row level security;

create policy "Users can view their own chance checks"
  on public.chance_checks for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can save their own chance checks"
  on public.chance_checks for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Users can update their own chance checks"
  on public.chance_checks for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "Users can delete their own chance checks"
  on public.chance_checks for delete to authenticated
  using ((select auth.uid()) = user_id);

-- ---------------------------------------------------------------------------
-- saved_programs: programs a user starred on /matches
-- ---------------------------------------------------------------------------
create table public.saved_programs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  school text not null,
  program text not null,
  match jsonb,                -- score snapshot {overall, academic, campus, social, ...}
  created_at timestamptz not null default now(),
  constraint saved_programs_user_school_program_key unique (user_id, school, program)
);

-- The unique constraint above already indexes (user_id, school, program);
-- this one serves the account page's "newest first" list.
create index saved_programs_user_id_created_at_idx
  on public.saved_programs (user_id, created_at desc);

alter table public.saved_programs enable row level security;

create policy "Users can view their own saved programs"
  on public.saved_programs for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can save programs for themselves"
  on public.saved_programs for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Users can update their own saved programs"
  on public.saved_programs for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "Users can delete their own saved programs"
  on public.saved_programs for delete to authenticated
  using ((select auth.uid()) = user_id);

-- ---------------------------------------------------------------------------
-- Data API access: signed-in users only (RLS still limits them to their rows)
-- ---------------------------------------------------------------------------
revoke all on table public.profiles, public.quiz_results, public.chance_checks, public.saved_programs from anon;
grant select, insert, update, delete
  on table public.profiles, public.quiz_results, public.chance_checks, public.saved_programs
  to authenticated;
