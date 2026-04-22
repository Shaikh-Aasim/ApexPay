import cors from "cors";
import express, { NextFunction, Request, Response } from "express";
import helmet from "helmet";
import { ZodError } from "zod";
import { env } from "./config/env";
import { notificationRoutes } from "./routes/notificationRoutes";
import { paymentRoutes } from "./routes/paymentRoutes";
import { testRoutes } from "./routes/testRoutes";
import { expireHolds, recoverStuckApproved } from "./services/paymentService";

const app = express();

app.use(helmet());
app.use(cors());
app.use(express.json({ limit: "1mb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.use("/payment", paymentRoutes);
app.use("/notifications", notificationRoutes);
app.use("/test", testRoutes);

app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  if (err instanceof ZodError) {
    res.status(400).json({ error: "VALIDATION_ERROR", details: err.flatten() });
    return;
  }
  const msg = err instanceof Error ? err.message : "UNKNOWN_ERROR";
  res.status(500).json({ error: msg });
});

app.listen(env.PORT, () => {
});

const HOLD_SWEEP_MS = 5_000;
const RECOVERY_SWEEP_MS = 5_000;

setInterval(() => {
  expireHolds().catch(() => undefined);
}, HOLD_SWEEP_MS);

setInterval(() => {
  recoverStuckApproved().catch(() => undefined);
}, RECOVERY_SWEEP_MS);
