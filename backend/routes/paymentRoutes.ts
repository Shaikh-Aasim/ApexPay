import { Router } from "express";
import * as paymentController from "../controllers/paymentController";

export const paymentRoutes = Router();

paymentRoutes.post("/initiate", paymentController.initiate);
paymentRoutes.post("/confirm", paymentController.confirm);
paymentRoutes.post("/cancel", paymentController.cancel);
paymentRoutes.get("/status", paymentController.status);

