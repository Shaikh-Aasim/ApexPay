import crypto from "crypto";
import { redis } from "../utils/redis";

function hashOtp(otp: string): string {
  return crypto.createHash("sha256").update(otp).digest("hex");
}

export async function issueOtp(args: { txnId: string; ttlSeconds: number }): Promise<string> {
  const otp = String(Math.floor(100000 + Math.random() * 900000));
  const payload = { hash: hashOtp(otp), attempts: 0 };
  await redis.set(`otp:txn:${args.txnId}`, JSON.stringify(payload), { ex: args.ttlSeconds });
  return otp;
}

export async function verifyOtp(args: { txnId: string; otp: string; maxAttempts: number }): Promise<void> {
  const key = `otp:txn:${args.txnId}`;
  const raw = await redis.get<string>(key);
  if (!raw) throw new Error("OTP_EXPIRED");
  const parsed = JSON.parse(raw) as { hash?: string; attempts?: number };
  const attempts = Number(parsed.attempts ?? 0);
  if (attempts >= args.maxAttempts) throw new Error("OTP_LOCKED");
  const ok = parsed.hash === hashOtp(args.otp);
  if (!ok) {
    await redis.set(key, JSON.stringify({ ...parsed, attempts: attempts + 1 }), { ex: 60 });
    throw new Error("OTP_INVALID");
  }
  await redis.del(key);
}

