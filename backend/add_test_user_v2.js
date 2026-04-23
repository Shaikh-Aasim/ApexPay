const { Pool } = require('pg');
const dotenv = require('dotenv');
const path = require('path');

// Load .env from current directory
dotenv.config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.DATABASE_URL.includes("supabase.com") ? { rejectUnauthorized: false } : undefined,
});

async function addTestUser() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    console.log("Adding user...");
    await client.query(`
      insert into users(id, full_name, phone)
      values ('33333333-3333-3333-3333-333333333333', 'Rahul Tester', '9000000003')
      on conflict (id) do nothing
    `);

    console.log("Adding account...");
    await client.query(`
      insert into accounts(id, user_id, bank_id, balance)
      select
        'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid,
        '33333333-3333-3333-3333-333333333333'::uuid,
        b.id,
        5000000.00
      from banks b
      where b.name = 'Apex Bank'
      on conflict (id) do nothing
    `);

    console.log("Adding VPA...");
    await client.query(`
      insert into vpas(user_id, bank_id, account_id, vpa)
      select
        '33333333-3333-3333-3333-333333333333'::uuid,
        b.id,
        'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid,
        'rahul@apex'
      from banks b
      where b.name = 'Apex Bank'
      on conflict (vpa) do nothing
    `);

    await client.query("COMMIT");
    console.log("Test user 'Rahul Tester' (rahul@apex) added successfully with ₹5,000,000 balance.");
  } catch (e) {
    await client.query("ROLLBACK");
    console.error("Error adding test user:", e);
  } finally {
    client.release();
    await pool.end();
  }
}

addTestUser();
