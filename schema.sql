-- Run once in Supabase: SQL Editor > New query > paste > Run
create table if not exists pp_submissions (
  team text not null,
  round int not null,
  members text,
  objective text,
  decisions jsonb,
  results jsonb,
  created timestamptz default now(),
  primary key (team, round)
);
create table if not exists pp_settings (k text primary key, v text);
create table if not exists pp_reflections (team text primary key, text text, created timestamptz default now());
insert into pp_settings (k, v) values ('max_round', '4') on conflict (k) do nothing;

-- Lock the tables down. The app uses the service_role key stored in Streamlit secrets, which bypasses RLS.
alter table pp_submissions enable row level security;
alter table pp_settings enable row level security;
alter table pp_reflections enable row level security;
