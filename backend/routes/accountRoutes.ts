import { Router } from "express";
import { getBalance } from "../controllers/accountController";

export const accountRoutes = Router();

accountRoutes.get("/balance", getBalance);
