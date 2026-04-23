import { pool } from "../utils/db";

export async function getBalanceByVPA(vpa: string): Promise<{ vpa: string; balance: number }> {
  const r = await pool.query(
    `select v.vpa, a.balance::float as balance
     from vpas v
     join accounts a on a.id = v.account_id
     where v.vpa = $1`,
    [vpa]
  );

  if (!r.rows[0]) {
    throw new Error("VPA_NOT_FOUND");
  }

  return {
    vpa: String(r.rows[0].vpa),
    balance: Number(r.rows[0].balance),
  };
}
