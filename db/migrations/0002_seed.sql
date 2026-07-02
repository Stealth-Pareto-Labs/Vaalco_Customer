-- =============================================================================
-- 0002_seed.sql — baseline tenant + vessel for the VAALCO demo. Idempotent.
-- =============================================================================

insert into public.tenants (id, name, slug)
values ('00000000-0000-0000-0000-0000000000a1', 'VAALCO Energy', 'vaalco')
on conflict (slug) do nothing;

insert into public.vessels (id, tenant_id, name, code, field_label, mgo_price_per_m3)
values (
    '00000000-0000-0000-0000-0000000000b1',
    '00000000-0000-0000-0000-0000000000a1',
    'Navigator Z',
    'NZ-MCT',
    'ETAME Field, Offshore Gabon',
    730
)
on conflict (tenant_id, code) do nothing;
