import { Router } from "express";
import { getBalance, resolveReceiver } from "../controllers/accountController";
import { authMiddleware } from "../middleware/authMiddleware";

export const accountRoutes = Router();

accountRoutes.get("/balance", authMiddleware as any, getBalance);
accountRoutes.get("/resolve", authMiddleware as any, resolveReceiver);
