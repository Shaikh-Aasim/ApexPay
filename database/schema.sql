create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'transaction_status') then
    create type transaction_status as enum (
      'REQUESTED',
      'HOLD',
      'APPROVED',
      'COMPLETED',
      'FAILED',
      'RECOVERED'
    );
  end if;

  if not exists (select 1 from pg_type where typname = 'fraud_type') then
    create type fraud_type as enum (
      'PHISHING',
      'QR_SCAM',
      'ACCOUNT_TAKEOVER',
      'MULE_ACCOUNT',
      'UNKNOWN'
    );
  end if;
end $$;

create table if not exists banks (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  phone text,
  created_at timestamptz not null default now()
);

create table if not exists accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  bank_id uuid not null references banks(id),
  balance numeric(14,2) not null check (balance >= 0),
  currency text not null default 'INR',
  created_at timestamptz not null default now(),
  unique (user_id, bank_id)
);

create table if not exists vpas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  bank_id uuid not null references banks(id),
  account_id uuid not null references accounts(id),
  vpa text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists receiver_profiles (
  receiver_user_id uuid primary key references users(id),
  suspicion_score real not null default 0,
  flagged boolean not null default false,
  updated_at timestamptz not null default now()
);

create table if not exists transactions (
  id uuid primary key default gen_random_uuid(),
  idempotency_key text unique,

  sender_user_id uuid not null references users(id),
  sender_account_id uuid not null references accounts(id),
  sender_vpa text not null,

  receiver_user_id uuid not null references users(id),
  receiver_account_id uuid not null references accounts(id),
  receiver_vpa text not null,

  amount numeric(14,2) not null check (amount > 0),
  status transaction_status not null default 'REQUESTED',

  risk_score real,
  decision text,
  decision_reason text,
  fraud_type fraud_type,
  model_version text,
  risk_features jsonb,

  otp_required boolean not null default false,
  hold_expires_at timestamptz,
  confirmed_at timestamptz,
  completed_at timestamptz,

  failure_reason text,
  retries int not null default 0,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_transactions_sender_created_at on transactions(sender_user_id, created_at desc);
create index if not exists idx_transactions_status on transactions(status);
create index if not exists idx_transactions_hold_expires_at on transactions(hold_expires_at) where status = 'HOLD';

create table if not exists risk_scores (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  txn_id uuid not null references transactions(id),
  risk_score real not null,
  decision text not null,
  decision_reason text,
  fraud_type fraud_type,
  model_version text,
  risk_features jsonb not null default '{}'::jsonb
);

create index if not exists idx_risk_scores_txn_id on risk_scores(txn_id);

create table if not exists audit_logs (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  txn_id uuid references transactions(id),
  actor_user_id uuid references users(id),
  action text not null,
  payload jsonb not null default '{}'::jsonb
);

create or replace function prevent_audit_log_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'audit_logs is immutable';
end $$;

drop trigger if exists audit_logs_prevent_update on audit_logs;
create trigger audit_logs_prevent_update
before update on audit_logs
for each row execute function prevent_audit_log_mutation();

drop trigger if exists audit_logs_prevent_delete on audit_logs;
create trigger audit_logs_prevent_delete
before delete on audit_logs
for each row execute function prevent_audit_log_mutation();

drop trigger if exists risk_scores_prevent_update on risk_scores;
create trigger risk_scores_prevent_update
before update on risk_scores
for each row execute function prevent_audit_log_mutation();

drop trigger if exists risk_scores_prevent_delete on risk_scores;
create trigger risk_scores_prevent_delete
before delete on risk_scores
for each row execute function prevent_audit_log_mutation();

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  type text not null,
  message text not null,
  created_at timestamptz not null default now(),
  read_at timestamptz
);

create index if not exists idx_notifications_user_created_at on notifications(user_id, created_at desc);

insert into banks(name)
values ('Apex Bank'), ('Neo Bank')
on conflict (name) do nothing;

insert into users(id, full_name, phone)
values
  ('11111111-1111-1111-1111-111111111111', 'Aarav Sender', '9000000001'),
  ('22222222-2222-2222-2222-222222222222', 'Isha Receiver', '9000000002')
on conflict (id) do nothing;

insert into accounts(id, user_id, bank_id, balance)
select
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
  '11111111-1111-1111-1111-111111111111'::uuid,
  b.id,
  200000.00
from banks b
where b.name = 'Apex Bank'
on conflict (id) do nothing;

insert into accounts(id, user_id, bank_id, balance)
select
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
  '22222222-2222-2222-2222-222222222222'::uuid,
  b.id,
  5000.00
from banks b
where b.name = 'Neo Bank'
on conflict (id) do nothing;

insert into vpas(user_id, bank_id, account_id, vpa)
select
  '11111111-1111-1111-1111-111111111111'::uuid,
  b.id,
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
  'aarav@apex'
from banks b
where b.name = 'Apex Bank'
on conflict (vpa) do nothing;

insert into vpas(user_id, bank_id, account_id, vpa)
select
  '22222222-2222-2222-2222-222222222222'::uuid,
  b.id,
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
  'isha@neo'
from banks b
where b.name = 'Neo Bank'
on conflict (vpa) do nothing;

insert into receiver_profiles(receiver_user_id, suspicion_score, flagged)
values
  ('22222222-2222-2222-2222-222222222222', 0.10, false)
on conflict (receiver_user_id) do update set
  suspicion_score = excluded.suspicion_score,
  flagged = excluded.flagged,
  updated_at = now();
