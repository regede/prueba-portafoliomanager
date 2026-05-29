-- ============================================================
-- PORTAFOLIO MANAGER — Schema Supabase
-- Ejecutar en: Supabase Dashboard → SQL Editor → New query
-- ============================================================

-- ── Tabla de perfiles (ligada a auth.users) ──────────────────
create table public.profiles (
  id               uuid primary key references auth.users(id) on delete cascade,
  email            text,
  plan             text not null default 'free' check (plan in ('free','pro','team')),
  stripe_customer_id      text,
  subscription_status     text default 'inactive',
  plan_expires_at         timestamptz,
  created_at       timestamptz default now()
);

-- Se crea automáticamente cuando alguien se registra
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Tabla de portafolios ──────────────────────────────────────
create table public.portfolios (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null references auth.users(id) on delete cascade,
  nombre      text not null default 'Mi Portafolio',
  config      jsonb not null default '{}',  -- título, evol_labels, evol_values, etc.
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- ── Posiciones USD ────────────────────────────────────────────
create table public.posiciones_usd (
  id            uuid primary key default gen_random_uuid(),
  portfolio_id  uuid not null references public.portfolios(id) on delete cascade,
  ticker        text not null,
  nombre        text not null,
  shares        numeric not null default 0,
  precio_entrada numeric not null default 0,
  monto         numeric not null default 0,
  sort_order    int default 0
);

-- ── Posiciones MXN / SIC ─────────────────────────────────────
create table public.posiciones_mxn (
  id            uuid primary key default gen_random_uuid(),
  portfolio_id  uuid not null references public.portfolios(id) on delete cascade,
  ticker        text not null,
  nombre        text not null,
  shares        numeric not null default 0,
  precio_entrada numeric not null default 0,
  costo_mxn     numeric not null default 0,
  sic_usd       boolean default false,
  sort_order    int default 0
);

-- ── Portafolios compartidos ───────────────────────────────────
create table public.portfolio_shares (
  id            uuid primary key default gen_random_uuid(),
  portfolio_id  uuid not null references public.portfolios(id) on delete cascade,
  shared_with   text not null,   -- email del invitado
  permiso       text not null default 'view' check (permiso in ('view','edit')),
  accepted      boolean default false,
  created_at    timestamptz default now()
);

-- ── Timestamps automáticos en portfolios ─────────────────────
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;
create trigger portfolios_updated_at
  before update on public.portfolios
  for each row execute function update_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY — cada usuario solo ve sus datos
-- ============================================================
alter table public.profiles          enable row level security;
alter table public.portfolios        enable row level security;
alter table public.posiciones_usd    enable row level security;
alter table public.posiciones_mxn    enable row level security;
alter table public.portfolio_shares  enable row level security;

-- profiles: solo el propio usuario
create policy "profiles: own" on public.profiles
  for all using (auth.uid() = id);

-- portfolios: dueño + invitados con acceso
create policy "portfolios: owner" on public.portfolios
  for all using (auth.uid() = owner_id);

create policy "portfolios: shared view" on public.portfolios
  for select using (
    exists (
      select 1 from public.portfolio_shares s
      where s.portfolio_id = id
        and s.shared_with = auth.email()
        and s.accepted = true
    )
  );

-- posiciones: a través del portfolio
create policy "pos_usd: via portfolio" on public.posiciones_usd
  for all using (
    exists (
      select 1 from public.portfolios p
      where p.id = portfolio_id and p.owner_id = auth.uid()
    )
  );

create policy "pos_mxn: via portfolio" on public.posiciones_mxn
  for all using (
    exists (
      select 1 from public.portfolios p
      where p.id = portfolio_id and p.owner_id = auth.uid()
    )
  );

-- portfolio_shares: solo el dueño gestiona invitaciones
create policy "shares: owner manages" on public.portfolio_shares
  for all using (
    exists (
      select 1 from public.portfolios p
      where p.id = portfolio_id and p.owner_id = auth.uid()
    )
  );

create policy "shares: invitee sees own" on public.portfolio_shares
  for select using (shared_with = auth.email());

-- ============================================================
-- LÍMITES POR PLAN (función helper para el frontend)
-- ============================================================
create or replace function public.get_plan_limits(user_plan text)
returns jsonb language sql as $$
  select case user_plan
    when 'free' then '{"max_portfolios":1,"max_positions":5,"price_interval_min":60}'::jsonb
    when 'pro'  then '{"max_portfolios":999,"max_positions":999,"price_interval_min":15}'::jsonb
    when 'team' then '{"max_portfolios":999,"max_positions":999,"price_interval_min":15,"max_members":5}'::jsonb
    else              '{"max_portfolios":1,"max_positions":5,"price_interval_min":60}'::jsonb
  end;
$$;
