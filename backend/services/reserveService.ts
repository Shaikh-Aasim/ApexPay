import crypto from "crypto";
import { acquireLock, redis, releaseLock } from "../utils/redis";
import { env } from "../config/env";

export async function reserveFunds(args: { accountId: string; amount: number; balanceLimit: number }): Promise<void> {
  const lockKey = `reserve_lock:${args.accountId}`;
  const lockValue = crypto.randomBytes(12).toString("hex");
  const ok = await acquireLock({ key: lockKey, value: lockValue, ttlMs: env.LOCK_TTL_MS });
  if (!ok) throw new Error("RESERVE_LOCKED");
  try {
    const key = `reserve:account:${args.accountId}`;
    const currentRaw = await redis.get<string>(key);
    const current = currentRaw ? Number(currentRaw) : 0;
    const next = current + args.amount;
    if (next > args.balanceLimit) throw new Error("INSUFFICIENT_FUNDS_RESERVED");
    await redis.set(key, String(next), { ex: 60 * 60 });
  } finally {
    await releaseLock({ key: lockKey, value: lockValue });
  }
}

export async function releaseReservedFunds(args: { accountId: string; amount: number }): Promise<void> {
  const lockKey = `reserve_lock:${args.accountId}`;
  const lockValue = crypto.randomBytes(12).toString("hex");
  const ok = await acquireLock({ key: lockKey, value: lockValue, ttlMs: env.LOCK_TTL_MS });
  if (!ok) return;
  try {
    const key = `reserve:account:${args.accountId}`;
    const currentRaw = await redis.get<string>(key);
    const current = currentRaw ? Number(currentRaw) : 0;
    const next = Math.max(0, current - args.amount);
    await redis.set(key, String(next), { ex: 60 * 60 });
  } finally {
    await releaseLock({ key: lockKey, value: lockValue });
  }
}
