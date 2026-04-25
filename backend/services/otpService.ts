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

export async function issueMobileOtp(args: { mobile: string; ttlSeconds: number; type: "REGISTER" | "LOGIN" }): Promise<string> {
  const otp = String(Math.floor(100000 + Math.random() * 900000));
  const payload = { hash: hashOtp(otp), attempts: 0 };
  const key = `otp:${args.type.toLowerCase()}:${args.mobile}`;
  
  console.log(`[OTP DEBUG] Issuing ${args.type} OTP for ${args.mobile}. Key: ${key}, OTP: ${otp}`);
  
  // Basic rate limiting/spam prevention: check if an OTP was recently sent
  const existing = await redis.get(key);
  if (existing) {
    console.log(`[OTP DEBUG] Existing OTP found for ${args.mobile}: ${JSON.stringify(existing)}`);
  }

  await redis.set(key, JSON.stringify(payload), { ex: args.ttlSeconds });
  return otp;
}

export async function verifyMobileOtp(args: { mobile: string; otp: string; maxAttempts: number; type: "REGISTER" | "LOGIN" }): Promise<void> {
  const key = `otp:${args.type.toLowerCase()}:${args.mobile}`;
  console.log(`[OTP DEBUG] Verifying ${args.type} OTP for ${args.mobile}. Key: ${key}`);
  const raw = await redis.get<unknown>(key);
  console.log(`[OTP DEBUG] Raw Redis value: ${JSON.stringify(raw)}`);
  if (!raw) throw new Error("OTP_EXPIRED");
  
  const parsed = typeof raw === "string" ? JSON.parse(raw) : (raw as any);
  const attempts = Number(parsed.attempts ?? 0);
  
  if (attempts >= args.maxAttempts) throw new Error("OTP_LOCKED");
  
  const ok = parsed.hash === hashOtp(args.otp);
  if (!ok) {
    await redis.set(key, JSON.stringify({ ...parsed, attempts: attempts + 1 }), { ex: 300 }); 
    throw new Error("OTP_INVALID");
  }
  
  if (args.type === "REGISTER") {
    const verifiedKey = `otp:verified:register:${args.mobile}`;
    console.log(`[OTP DEBUG] Verification SUCCESS. Setting flag: ${verifiedKey}`);
    await redis.set(verifiedKey, "true", { ex: 600 }); 
  }
  
  await redis.del(key);
}

export async function checkOtpVerified(mobile: string): Promise<boolean> {
  const key = `otp:verified:register:${mobile}`;
  const val = await redis.get(key);
  console.log(`[OTP DEBUG] Checking verification for ${mobile}. Raw value from Redis:`, val, "Type:", typeof val);
  
  // Handle both string "true" and boolean true
  return val === "true" || val === true;
}

export async function clearOtpVerified(mobile: string): Promise<void> {
  await redis.del(`otp:verified:register:${mobile}`);
}

export async function verifyOtp(args: { txnId: string; otp: string; maxAttempts: number }): Promise<void> {
  const key = `otp:txn:${args.txnId}`;
  const raw = await redis.get<unknown>(key);
  if (!raw) throw new Error("OTP_EXPIRED");
  const parsed =
    typeof raw === "string" ? (JSON.parse(raw) as { hash?: string; attempts?: number }) : (raw as { hash?: string; attempts?: number });
  const attempts = Number(parsed.attempts ?? 0);
  if (attempts >= args.maxAttempts) throw new Error("OTP_LOCKED");
  const ok = parsed.hash === hashOtp(args.otp);
  if (!ok) {
    await redis.set(key, JSON.stringify({ ...parsed, attempts: attempts + 1 }), { ex: 60 });
    throw new Error("OTP_INVALID");
  }
  await redis.del(key);
}
