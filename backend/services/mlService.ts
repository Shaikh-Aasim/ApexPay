import { z } from "zod";
import { env } from "../config/env";

export const fraudTypeSchema = z.enum(["PHISHING", "QR_SCAM", "ACCOUNT_TAKEOVER", "MULE_ACCOUNT", "UNKNOWN"]);
export type FraudType = z.infer<typeof fraudTypeSchema>;

export const decisionSchema = z.enum(["LOW", "MEDIUM", "HIGH"]);
export type RiskDecision = z.infer<typeof decisionSchema>;

export const riskRequestSchema = z.object({
  amount: z.number().positive(),
  txn_count_24h: z.number().int().nonnegative(),
  device_change: z.number().int().min(0).max(1),
  location_anomaly: z.number().int().min(0).max(1),
  receiver_suspicion_score: z.number().min(0).max(1),
  receiver_flagged: z.number().int().min(0).max(1),
  user_avg_amount_30d: z.number().nonnegative(),
  user_std_amount_30d: z.number().positive(),
  amount_zscore: z.number(),
});
export type RiskRequest = z.infer<typeof riskRequestSchema>;

const riskResponseSchema = z.object({
  risk_score: z.number().min(0).max(1),
  decision: decisionSchema,
  reasons: z.array(z.string()),
  fraud_type: fraudTypeSchema,
  model_version: z.string(),
});
export type RiskResponse = z.infer<typeof riskResponseSchema>;

export async function predictRisk(payload: RiskRequest): Promise<RiskResponse> {
  const url = new URL("/predict-risk", env.ML_SERVICE_URL).toString();
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`ML_SERVICE_${res.status}`);
  }
  const data = (await res.json()) as unknown;
  return riskResponseSchema.parse(data);
}

