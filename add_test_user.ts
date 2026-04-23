import { pool } from "./backend/utils/db";

async function addTestUser() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    // 1. Add User
    await client.query(`
      insert into users(id, full_name, phone)
      values ('33333333-3333-3333-3333-333333333333', 'Rahul Tester', '9000000003')
      on conflict (id) do nothing
    `);

    // 2. Add Account
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

    // 3. Add VPA
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
