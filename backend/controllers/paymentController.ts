import { Request, Response } from "express";
import { z } from "zod";
import { cancelPayment, confirmPayment, getPaymentStatus, initiatePayment } from "../services/paymentService";

const initiateSchema = z.object({
  idempotencyKey: z.string().optional(),
  senderVpa: z.string().min(3),
  receiverVpa: z.string().min(3),
  amount: z.number().positive(),
  deviceId: z.string().min(1),
  location: z.string().min(1),
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

export async function initiate(req: Request, res: Response): Promise<void> {
  const body = initiateSchema.parse(req.body);
  const result = await initiatePayment(body);
  res.json(result);
}

export async function confirm(req: Request, res: Response): Promise<void> {
  const body = confirmSchema.parse(req.body);
  await confirmPayment(body);
  const status = await getPaymentStatus(body.txnId);
  res.json(status);
}

export async function cancel(req: Request, res: Response): Promise<void> {
  const body = cancelSchema.parse(req.body);
  await cancelPayment(body);
  const status = await getPaymentStatus(body.txnId);
  res.json(status);
}

export async function status(req: Request, res: Response): Promise<void> {
  const txnId = z.string().min(1).parse(req.query.id);
  const s = await getPaymentStatus(txnId);
  res.json(s);
}

