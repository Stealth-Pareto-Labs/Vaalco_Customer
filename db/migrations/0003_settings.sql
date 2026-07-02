-- =============================================================================
-- 0003_settings.sql — per-tenant application settings (e.g. alert recipients).
-- =============================================================================

create table if not exists public.app_settings (
    tenant_id   uuid not null references public.tenants(id) on delete cascade,
    key         text not null,
    value       jsonb not null default '{}',
    updated_at  timestamptz not null default now(),
    primary key (tenant_id, key)
);

alter table public.app_settings enable row level security;

drop policy if exists app_settings_tenant_read on public.app_settings;
create policy app_settings_tenant_read on public.app_settings
    for select using (tenant_id = public.current_tenant_id());
