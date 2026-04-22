import { Request, Response } from "express";
import { z } from "zod";
import { getUserNotifications } from "../services/notificationService";

export async function list(req: Request, res: Response): Promise<void> {
  const userId = z.string().min(1).parse(req.query.userId);
  const items = await getUserNotifications(userId);
  res.json({ items });
}

