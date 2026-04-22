import { pool } from "../utils/db";
import { redis } from "../utils/redis";

export async function getTxnCount24h(senderUserId: string): Promise<number> {
  const r = await pool.query(
    `select count(*)::int as c
     from transactions
     where sender_user_id = $1
       and created_at >= now() - interval '24 hours'`,
    [senderUserId]
  );
  return Number(r.rows[0]?.c ?? 0);
}

export async function getUserAmountStats30d(senderUserId: string): Promise<{ avg: number; std: number }> {
  const r = await pool.query(
    `select
        coalesce(avg(amount)::float, 0) as avg_amount,
        coalesce(stddev_pop(amount)::float, 0) as std_amount
     from transactions
     where sender_user_id = $1
       and status in ('COMPLETED', 'RECOVERED')
       and created_at >= now() - interval '30 days'`,
    [senderUserId]
  );
  const avg = Number(r.rows[0]?.avg_amount ?? 0);
  const std = Number(r.rows[0]?.std_amount ?? 0);
  return { avg, std };
}

export async function computeDeviceChange(userId: string, deviceId: string): Promise<number> {
  const key = `user:last_device:${userId}`;
  const last = await redis.get<string>(key);
  return last && last !== deviceId ? 1 : 0;
}

export async function computeLocationAnomaly(userId: string, location: string): Promise<number> {
  const key = `user:last_location:${userId}`;
  const last = await redis.get<string>(key);
  return last && last !== location ? 1 : 0;
}

export async function updateBehaviorAnchors(args: { userId: string; deviceId: string; location: string }): Promise<void> {
  await Promise.all([
    redis.set(`user:last_device:${args.userId}`, args.deviceId, { ex: 60 * 60 * 24 * 30 }),
    redis.set(`user:last_location:${args.userId}`, args.location, { ex: 60 * 60 * 24 * 30 }),
  ]);
}

