import { Request, Response } from "express";
import { z } from "zod";
import { setCrashPoint, setDelayMs } from "../services/chaosService";

const delaySchema = z.object({
  ms: z.number().int().min(0).max(60_000),
  ttlSeconds: z.number().int().min(1).max(3600).default(60),
});

const crashSchema = z.object({
  point: z.enum(["NONE", "BEFORE_DEBIT", "AFTER_DEBIT"]),
  ttlSeconds: z.number().int().min(1).max(3600).default(60),
});

export async function delay(req: Request, res: Response): Promise<void> {
  const body = delaySchema.parse(req.body);
  await setDelayMs(body);
  res.json({ ok: true });
}

export async function crash(req: Request, res: Response): Promise<void> {
  const body = crashSchema.parse(req.body);
  await setCrashPoint(body);
  res.json({ ok: true });
}

