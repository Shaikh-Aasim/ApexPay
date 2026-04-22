import { Redis } from "@upstash/redis";
import { env } from "../config/env";

export const redis = new Redis({
  url: env.UPSTASH_REDIS_REST_URL,
  token: env.UPSTASH_REDIS_REST_TOKEN,
});

export async function acquireLock(args: { key: string; value: string; ttlMs: number }): Promise<boolean> {
  const res = await redis.set(args.key, args.value, { nx: true, px: args.ttlMs });
  return res === "OK";
}

export async function releaseLock(args: { key: string; value: string }): Promise<void> {
  const script = `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end`;
  await redis.eval(script, [args.key], [args.value]);
}

export async function getJson<T>(key: string): Promise<T | null> {
  const raw = await redis.get<unknown>(key);
  if (!raw) return null;
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }
  if (typeof raw === "object") return raw as T;
  return null;
}

export async function setJson(key: string, value: unknown, ttlSeconds?: number): Promise<void> {
  const payload = JSON.stringify(value);
  if (ttlSeconds && ttlSeconds > 0) {
    await redis.set(key, payload, { ex: ttlSeconds });
    return;
  }
  await redis.set(key, payload);
}
