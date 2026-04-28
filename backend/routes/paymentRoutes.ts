import { Router } from "express";
import * as paymentController from "../controllers/paymentController";
import { authMiddleware } from "../middleware/authMiddleware";

export const paymentRoutes = Router();

// Secure these routes with JWT
paymentRoutes.post("/initiate", authMiddleware as any, paymentController.initiate);
paymentRoutes.post("/confirm", authMiddleware as any, paymentController.confirm);
paymentRoutes.post("/cancel", authMiddleware as any, paymentController.cancel);
paymentRoutes.get("/history", authMiddleware as any, paymentController.history);
paymentRoutes.get("/status", paymentController.status); // Status might be public for tracking

