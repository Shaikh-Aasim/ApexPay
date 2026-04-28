import { Request, Response } from "express";
import { z } from "zod";
import { AuthRequest } from "../middleware/authMiddleware";
import { cancelPayment, confirmPayment, getPaymentStatus, getTransactionHistory, initiatePayment } from "../services/paymentService";

const initiateSchema = z.object({
  idempotencyKey: z.string().optional(),
  senderVpa: z.string().optional(),
  receiverVpa: z.string().min(3).optional(),
  receiverMobile: z.string().min(10).optional(),
  amount: z.number().positive(),
  deviceId: z.string().min(1),
  location: z.string().min(1),
  pin: z.string().optional(),
  paymentNote: z.string().optional(),
}).refine(data => data.receiverVpa || data.receiverMobile, {
  message: "Either receiverVpa or receiverMobile must be provided",
  path: ["receiverVpa"]
});

const confirmSchema = z.object({
  txnId: z.string().min(1),
  otp: z.string().min(4),
  pin: z.string().min(1),
});

const cancelSchema = z.object({
  txnId: z.string().min(1),
  actorUserId: z.string().optional(),
});

export async function initiate(req: AuthRequest, res: Response): Promise<void> {
  const body = initiateSchema.parse(req.body);
  console.log(`Payment initiated by user: ${req.user?.userId} (${req.user?.name})`);
  const result = await initiatePayment({
    ...body,
    senderUserId: req.user?.userId,
  });
  res.json(result);
}

export async function confirm(req: AuthRequest, res: Response): Promise<void> {
  const body = confirmSchema.parse(req.body);
  await confirmPayment(body);
  const status = await getPaymentStatus(body.txnId);
  res.json(status);
}

export async function cancel(req: AuthRequest, res: Response): Promise<void> {
  const body = cancelSchema.parse(req.body);
  await cancelPayment({ ...body, actorUserId: req.user?.userId });
  const status = await getPaymentStatus(body.txnId);
  res.json(status);
}

export async function status(req: Request, res: Response): Promise<void> {
  const txnId = z.string().min(1).parse(req.query.id);
  const s = await getPaymentStatus(txnId);
  res.json(s);
}

export async function history(req: AuthRequest, res: Response): Promise<void> {
  const userId = req.user?.userId;
  if (!userId) {
    res.status(401).json({ error: "UNAUTHORIZED" });
    return;
  }
  const items = await getTransactionHistory(userId);
  res.json({ items });
}

