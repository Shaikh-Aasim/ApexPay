import { Router } from "express";
import * as notificationController from "../controllers/notificationController";

export const notificationRoutes = Router();

notificationRoutes.get("/", notificationController.list);

