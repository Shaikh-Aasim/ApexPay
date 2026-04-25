import cors from "cors";
import express, { NextFunction, Request, Response } from "express";
import helmet from "helmet";
import { ZodError } from "zod";
import { env } from "./config/env";
import { accountRoutes } from "./routes/accountRoutes";
import authRoutes from "./routes/authRoutes";
import bankRoutes from "./routes/bankRoutes";
import { notificationRoutes } from "./routes/notificationRoutes";
import { paymentRoutes } from "./routes/paymentRoutes";
import { testRoutes } from "./routes/testRoutes";
import { expireHolds, recoverStuckApproved } from "./services/paymentService";
import { runMigrations } from "./utils/migrate";

const app = express();

app.use(helmet());
app.use(cors());
app.use(express.json({ limit: "1mb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.use("/api/auth", authRoutes);
app.use("/api/bank", bankRoutes);
app.use("/payment", paymentRoutes);
app.use("/account", accountRoutes);
app.use("/notifications", notificationRoutes);
app.use("/test", testRoutes);

app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  console.error(err);
  if (err instanceof ZodError) {
    res.status(400).json({ error: "VALIDATION_ERROR", details: err.flatten() });
    return;
  }
  const msg = err instanceof Error ? err.message : "UNKNOWN_ERROR";
  res.status(500).json({ error: msg });
});

async function startServer() {
  await runMigrations();
  app.listen(env.PORT, () => {
    console.log(`Server running on port ${env.PORT}`);
  });
}

startServer();

const HOLD_SWEEP_MS = 5_000;
const RECOVERY_SWEEP_MS = 5_000;

setInterval(() => {
  expireHolds().catch(() => undefined);
}, HOLD_SWEEP_MS);

setInterval(() => {
  recoverStuckApproved().catch(() => undefined);
}, RECOVERY_SWEEP_MS);
