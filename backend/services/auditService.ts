import { pool } from "../utils/db";

export async function auditLog(args: {
  txnId?: string;
  actorUserId?: string;
  action: string;
  payload?: Record<string, unknown>;
}): Promise<void> {
  await pool.query(
    `insert into audit_logs(txn_id, actor_user_id, action, payload)
     values ($1, $2, $3, $4::jsonb)`,
    [args.txnId ?? null, args.actorUserId ?? null, args.action, JSON.stringify(args.payload ?? {})]
  );
}

