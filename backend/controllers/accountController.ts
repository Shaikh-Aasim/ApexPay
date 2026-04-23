import { Request, Response } from "express";
import { z } from "zod";
import { getBalanceByVPA } from "../services/accountService";

const balanceQuerySchema = z.object({
  vpa: z.string().min(3),
});

export async function getBalance(req: Request, res: Response): Promise<void> {
  try {
    const { vpa } = balanceQuerySchema.parse(req.query);
    const result = await getBalanceByVPA(vpa);
    res.json({
      success: true,
      ...result,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.message === "VPA_NOT_FOUND") {
      res.status(404).json({
        success: false,
        error: "VPA_NOT_FOUND",
      });
      return;
    }
    throw err; // Let global error handler handle other errors (like ZodError)
  }
}
