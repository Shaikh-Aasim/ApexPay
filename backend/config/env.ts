import { config as loadDotenv } from "dotenv";
import { z } from "zod";

loadDotenv();

const schema = z.object({
  PORT: z.coerce.number().int().positive().default(4000),
  DATABASE_URL: z.string().min(1),
  ML_SERVICE_URL: z.string().min(1).default("http://localhost:8000"),
  UPSTASH_REDIS_REST_URL: z.string().min(1),
  UPSTASH_REDIS_REST_TOKEN: z.string().min(1),
  HOLD_TTL_SECONDS: z.coerce.number().int().positive().default(45),
  LOCK_TTL_MS: z.coerce.number().int().positive().default(8000),
});

export const env = schema.parse(process.env);
