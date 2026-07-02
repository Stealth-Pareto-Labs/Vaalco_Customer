-- =============================================================================
-- 0001_init.sql — VAALCO Fuel Intelligence core schema
-- Multi-tenant, row-level-security-protected. Idempotent (safe to re-run).
-- =============================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Tenants (customers) and vessels
-- ---------------------------------------------------------------------------
create table if not exists public.tenants (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    slug        text unique not null,
    created_at  timestamptz not null default now()
);

create table if not exists public.vessels (
    id                uuid primary key default gen_random_uuid(),
    tenant_id         uuid not null references public.tenants(id) on delete cascade,
    name              text not null,               -- "Navigator Z"
    code              text not null,               -- "NZ-MCT"
    field_label       text,                        -- "ETAME Field, Offshore Gabon"
    mgo_price_per_m3  numeric not null default 730,
    created_at        timestamptz not null default now(),
    unique (tenant_id, code)
);

-- ---------------------------------------------------------------------------
-- User profiles (linked to Supabase auth.users), roles, and locale
-- ---------------------------------------------------------------------------
do $$ begin
    create type public.user_role as enum ('admin', 'ops_manager', 'captain');
exception when duplicate_object then null; end $$;

create table if not exists public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    tenant_id   uuid references public.tenants(id) on delete set null,
    full_name   text,
    role        public.user_role not null default 'captain',
    locale      text not null default 'en',        -- 'en' | 'fr'
    created_at  timestamptz not null default now()
);

-- Auto-create a profile row when a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    insert into public.profiles (id, full_name)
    values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.email))
    on conflict (id) do nothing;
    return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- Helper: the tenant of the currently-authenticated user (used by RLS).
create or replace function public.current_tenant_id()
returns uuid language sql stable security definer set search_path = public as $$
    select tenant_id from public.profiles where id = auth.uid()
$$;

-- ---------------------------------------------------------------------------
-- Raw ingested report files (one row per uploaded .xlsx)
-- ---------------------------------------------------------------------------
do $$ begin
    create type public.report_status as enum ('pending', 'parsed', 'failed');
exception when duplicate_object then null; end $$;

create table if not exists public.raw_reports (
    id            uuid primary key default gen_random_uuid(),
    tenant_id     uuid not null references public.tenants(id) on delete cascade,
    vessel_id     uuid not null references public.vessels(id) on delete cascade,
    report_date   date,
    source_file   text not null,
    storage_path  text not null,                   -- path in the raw-reports bucket
    file_hash     text not null,                   -- sha256 for idempotency
    status        public.report_status not null default 'pending',
    error         text,
    ingested_at   timestamptz not null default now(),
    unique (vessel_id, file_hash)
);

-- ---------------------------------------------------------------------------
-- Normalized daily records (deterministic parse output per vessel-day)
-- ---------------------------------------------------------------------------
create table if not exists public.daily_records (
    id             uuid primary key default gen_random_uuid(),
    tenant_id      uuid not null references public.tenants(id) on delete cascade,
    vessel_id      uuid not null references public.vessels(id) on delete cascade,
    raw_report_id  uuid references public.raw_reports(id) on delete set null,
    report_date    date not null,
    fuel_l         numeric,
    dp_hours       numeric,
    resid_l        numeric,
    payload        jsonb not null default '{}',    -- full enriched record from analysis.ingest()
    created_at     timestamptz not null default now(),
    unique (vessel_id, report_date)
);

-- ---------------------------------------------------------------------------
-- Analysis runs (one per intelligence.run()) and their signals
-- ---------------------------------------------------------------------------
create table if not exists public.analysis_runs (
    id                 uuid primary key default gen_random_uuid(),
    tenant_id          uuid not null references public.tenants(id) on delete cascade,
    vessel_id          uuid not null references public.vessels(id) on delete cascade,
    run_id             text not null,               -- app-generated run id (e.g. 20260701T203200)
    trigger            text,
    as_of              text,
    headline           text,
    executive_summary  text,
    reports_loaded     int,
    counts             jsonb not null default '{}', -- {high, medium, low, total}
    payload            jsonb not null default '{}', -- full run object (source of truth for the UI)
    generated_at       timestamptz not null default now(),
    unique (vessel_id, run_id)
);

create table if not exists public.signals (
    id            uuid primary key default gen_random_uuid(),
    tenant_id     uuid not null references public.tenants(id) on delete cascade,
    vessel_id     uuid not null references public.vessels(id) on delete cascade,
    run_id        uuid not null references public.analysis_runs(id) on delete cascade,
    priority      text not null,                    -- 'high' | 'medium' | 'low'
    category      text,
    title         text,
    explanation   text,
    evidence      jsonb not null default '[]',
    next_steps    jsonb not null default '[]',
    probe         text,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Notifications log + ingestion job tracking
-- ---------------------------------------------------------------------------
create table if not exists public.notifications_log (
    id           uuid primary key default gen_random_uuid(),
    tenant_id    uuid not null references public.tenants(id) on delete cascade,
    vessel_id    uuid references public.vessels(id) on delete set null,
    run_id       uuid references public.analysis_runs(id) on delete set null,
    channel      text not null,                     -- 'email' | 'sms'
    recipients   jsonb not null default '[]',
    status       text not null,                     -- 'sent' | 'simulated' | 'failed'
    detail       text,
    created_at   timestamptz not null default now()
);

do $$ begin
    create type public.job_status as enum ('queued', 'running', 'done', 'failed');
exception when duplicate_object then null; end $$;

create table if not exists public.ingestion_jobs (
    id            uuid primary key default gen_random_uuid(),
    tenant_id     uuid not null references public.tenants(id) on delete cascade,
    vessel_id     uuid not null references public.vessels(id) on delete cascade,
    storage_path  text not null,
    source_file   text,
    status        public.job_status not null default 'queued',
    attempts      int not null default 0,
    error         text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes for common queries
-- ---------------------------------------------------------------------------
create index if not exists idx_daily_records_vessel_date on public.daily_records (vessel_id, report_date desc);
create index if not exists idx_analysis_runs_vessel_gen on public.analysis_runs (vessel_id, generated_at desc);
create index if not exists idx_signals_run on public.signals (run_id);
create index if not exists idx_raw_reports_vessel on public.raw_reports (vessel_id, report_date desc);
create index if not exists idx_jobs_status on public.ingestion_jobs (status, created_at);

-- ---------------------------------------------------------------------------
-- Row-Level Security: every tenant sees only its own rows.
-- (The API/workers use the service_role key, which bypasses RLS.)
-- ---------------------------------------------------------------------------
alter table public.tenants           enable row level security;
alter table public.vessels           enable row level security;
alter table public.profiles          enable row level security;
alter table public.raw_reports       enable row level security;
alter table public.daily_records     enable row level security;
alter table public.analysis_runs     enable row level security;
alter table public.signals           enable row level security;
alter table public.notifications_log enable row level security;
alter table public.ingestion_jobs    enable row level security;

-- profiles: a user can read/update their own profile
drop policy if exists profiles_self on public.profiles;
create policy profiles_self on public.profiles
    for all using (id = auth.uid()) with check (id = auth.uid());

-- tenants: members can read their tenant
drop policy if exists tenants_read on public.tenants;
create policy tenants_read on public.tenants
    for select using (id = public.current_tenant_id());

-- generic tenant-scoped read policies for the frontend
do $$
declare t text;
begin
    foreach t in array array[
        'vessels','raw_reports','daily_records','analysis_runs','signals',
        'notifications_log','ingestion_jobs'
    ] loop
        execute format('drop policy if exists %I_tenant_read on public.%I;', t, t);
        execute format(
            'create policy %I_tenant_read on public.%I for select using (tenant_id = public.current_tenant_id());',
            t, t);
    end loop;
end $$;

-- ---------------------------------------------------------------------------
-- Storage buckets (private) for raw files and rendered reports
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('raw-reports', 'raw-reports', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('intelligence-runs', 'intelligence-runs', false)
on conflict (id) do nothing;
