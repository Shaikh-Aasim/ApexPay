import { Request, Response } from "express";
import { z } from "zod";
import * as bankService from "../services/bankService";

const CreateAccountSchema = z.object({
  firstName: z.string().min(1),
  lastName: z.string().min(1),
  aadharNumber: z.string().min(12).max(12),
  mobileNumber: z.string().min(10),
  accountNumber: z.string().min(5),
  bankId: z.string().uuid(),
  ifscCode: z.string().min(4), // Relaxed from 11 to 4 for simulation
  balance: z.number().min(0).default(1000),
});

export const createAccount = async (req: Request, res: Response) => {
  const data = CreateAccountSchema.parse(req.body);
  const account = await bankService.createBankAccount(data);
  res.json({ ok: true, accountId: account.id });
};

export const getBanks = async (_req: Request, res: Response) => {
  const banks = await bankService.getAllBanks();
  res.json({ ok: true, banks });
};
