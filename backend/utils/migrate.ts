import { pool } from "./db";

export async function runMigrations() {
  console.log("Running database migrations...");
  const client = await pool.connect();
  try {
    // 1. Ensure 'users' table has correct columns
    await client.query(`
      do $$ 
      begin 
        -- Add mobile_number if missing
        if not exists (select 1 from information_schema.columns where table_name='users' and column_name='mobile_number') then
          alter table users add column mobile_number text unique;
        end if;

        -- Add pin_hash if missing
        if not exists (select 1 from information_schema.columns where table_name='users' and column_name='pin_hash') then
          alter table users add column pin_hash text;
        end if;

        -- Add first_name if missing
        if not exists (select 1 from information_schema.columns where table_name='users' and column_name='first_name') then
          alter table users add column first_name text;
        end if;

        -- Add last_name if missing
        if not exists (select 1 from information_schema.columns where table_name='users' and column_name='last_name') then
          alter table users add column last_name text;
        end if;

        -- Add full_name if missing, or drop not null if it exists
        if not exists (select 1 from information_schema.columns where table_name='users' and column_name='full_name') then
          alter table users add column full_name text;
        else
          alter table users alter column full_name drop not null;
        end if;
      end $$;
    `);

    // 2. Ensure 'bank_accounts' table exists
    await client.query(`
      create table if not exists banks (
        id uuid primary key default gen_random_uuid(),
        name text not null unique,
        created_at timestamptz not null default now()
      );

      create table if not exists bank_accounts (
        id uuid primary key default gen_random_uuid(),
        first_name text,
        last_name text,
        aadhar_number text,
        mobile_number text not null,
        account_number text not null unique,
        bank_id uuid not null references banks(id),
        ifsc_code text,
        balance numeric(14,2) not null check (balance >= 0),
        created_at timestamptz not null default now()
      );
    `);

    // 3. Update bank_accounts if columns are missing (for existing tables)
    await client.query(`
      do $$ 
      begin 
        if not exists (select 1 from information_schema.columns where table_name='bank_accounts' and column_name='first_name') then
          alter table bank_accounts add column first_name text, add column last_name text, add column aadhar_number text, add column ifsc_code text;
        end if;

        if not exists (select 1 from information_schema.columns where table_name='transactions' and column_name='payment_note') then
          alter table transactions add column payment_note text;
        end if;
      end $$;
    `);

    // 3. Seed banks and bank accounts if they don't exist
    await client.query(`
      insert into banks(name) values ('Apex Bank'), ('Neo Bank') on conflict (name) do nothing;
      
      insert into bank_accounts(mobile_number, account_number, bank_id, balance)
      select '9000000001', 'ACT-111111', id, 250000.00 from banks where name = 'Apex Bank'
      on conflict (account_number) do nothing;

      insert into bank_accounts(mobile_number, account_number, bank_id, balance)
      select '9000000002', 'ACT-222222', id, 10000.00 from banks where name = 'Neo Bank'
      on conflict (account_number) do nothing;
    `);

    console.log("Migrations completed successfully.");
  } catch (err) {
    console.error("Migration failed:", err);
  } finally {
    client.release();
  }
}
