import { pool } from "../utils/db";

export async function getReceiverRisk(receiverUserId: string): Promise<{ suspicionScore: number; flagged: boolean }> {
  const r = await pool.query(`select suspicion_score::float as suspicion_score, flagged from receiver_profiles where receiver_user_id = $1`, [
    receiverUserId,
  ]);
  if (!r.rows[0]) return { suspicionScore: 0, flagged: false };
  return { suspicionScore: Number(r.rows[0].suspicion_score), flagged: Boolean(r.rows[0].flagged) };
}

