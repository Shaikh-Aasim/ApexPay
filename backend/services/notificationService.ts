import { pool } from "../utils/db";

export async function notifyUser(args: { userId: string; type: string; message: string }): Promise<void> {
  await pool.query(`insert into notifications(user_id, type, message) values ($1, $2, $3)`, [
    args.userId,
    args.type,
    args.message,
  ]);
}

export async function getUserNotifications(userId: string): Promise<Array<{ id: string; type: string; message: string; created_at: string }>> {
  const r = await pool.query(
    `select id::text, type, message, created_at::text
     from notifications
     where user_id = $1
     order by created_at desc
     limit 20`,
    [userId]
  );
  return r.rows as Array<{ id: string; type: string; message: string; created_at: string }>;
}

