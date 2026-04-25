import { Request, Response } from "express";
import { z } from "zod";
import { getBalanceByVPA } from "../services/accountService";
import { AuthRequest } from "../middleware/authMiddleware";
import { pool } from "../utils/db";
import bcrypt from "bcrypt";

const balanceQuerySchema = z.object({
  vpa: z.string().min(3).optional(),
  pin: z.string().min(4).optional(),
});

const resolveQuerySchema = z.object({
  vpa: z.string().optional(),
  mobile: z.string().optional(),
}).refine(data => data.vpa || data.mobile, {
  message: "Either vpa or mobile must be provided"
});

export async function resolveReceiver(req: Request, res: Response): Promise<void> {
  try {
    const { vpa, mobile } = resolveQuerySchema.parse(req.query);
    
    let query = "";
    let params: any[] = [];
    
    if (vpa) {
      query = `
        select u.first_name, u.last_name, v.vpa 
        from vpas v 
        join users u on u.id = v.user_id 
        where v.vpa = $1 
        limit 1
      `;
      params = [vpa];
    } else if (mobile) {
      query = `
        select u.first_name, u.last_name, v.vpa 
        from users u 
        join vpas v on v.user_id = u.id 
        where u.mobile_number = $1 
        order by v.created_at desc 
        limit 1
      `;
      params = [mobile];
    }
    
    const result = await pool.query(query, params);
    
    if (result.rows.length === 0) {
      res.status(404).json({ success: false, error: "RECEIVER_NOT_FOUND" });
      return;
    }
    
    const row = result.rows[0];
    res.json({
      success: true,
      name: `${row.first_name} ${row.last_name}`,
      vpa: row.vpa
    });
  } catch (err) {
    throw err;
  }
}

export async function getBalance(req: AuthRequest, res: Response): Promise<void> {
  try {
    const { vpa, pin } = balanceQuerySchema.parse(req.query);

    // If no VPA is provided, use the authenticated user's VPA
    let targetVpa = vpa;
    if (!targetVpa && req.user?.userId) {
      if (!pin) {
        res.status(400).json({ success: false, error: "PIN_REQUIRED" });
        return;
      }

      // Verify PIN for self-balance check
      const userResult = await pool.query("select pin_hash, first_name, mobile_number from users where id = $1", [req.user.userId]);
      const user = userResult.rows[0];
      if (!user) {
        res.status(404).json({ success: false, error: "USER_NOT_FOUND" });
        return;
      }

      const pinOk = await bcrypt.compare(pin, user.pin_hash);
      if (!pinOk) {
        res.status(401).json({ success: false, error: "INVALID_PIN" });
        return;
      }

      const vpaResult = await pool.query("select vpa from vpas where user_id = $1 limit 1", [req.user.userId]);
      targetVpa = vpaResult.rows[0]?.vpa;

      // Fallback if no VPA in DB but user is valid (sync with login fallback)
      if (!targetVpa) {
        const fallbackVpa = `${user.first_name.toLowerCase()}${user.mobile_number.slice(-4)}@apex`;
        
        // Try to get balance directly from account if VPA missing
        const accResult = await pool.query("select balance::float from accounts where user_id = $1 limit 1", [req.user.userId]);
        if (accResult.rows[0]) {
          res.json({
            success: true,
            vpa: fallbackVpa,
            balance: accResult.rows[0].balance
          });
          return;
        }
      }
    }

    if (!targetVpa) {
      res.status(400).json({ success: false, error: "VPA_REQUIRED" });
      return;
    }

    const result = await getBalanceByVPA(targetVpa);
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
