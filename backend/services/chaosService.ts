import { redis } from "../utils/redis";

export type CrashPoint = "NONE" | "BEFORE_DEBIT" | "AFTER_DEBIT" | "BEFORE_CREDIT";

export async function setDelayMs(args: { ms: number; ttlSeconds: number }): Promise<void> {
  await redis.set("chaos:delay_ms", String(args.ms), { ex: Math.max(1, args.ttlSeconds) });
}

export async function getDelayMs(): Promise<number> {
  const raw = await redis.get<string>("chaos:delay_ms");
  return raw ? Number(raw) : 0;
}

export async function setCrashPoint(args: { point: CrashPoint; ttlSeconds: number }): Promise<void> {
  await redis.set("chaos:crash_point", args.point, { ex: Math.max(1, args.ttlSeconds) });
}

export async function getCrashPoint(): Promise<CrashPoint> {
  const raw = await redis.get<string>("chaos:crash_point");
  if (raw === "BEFORE_DEBIT" || raw === "AFTER_DEBIT" || raw === "NONE") return raw;
  return "NONE";
}

