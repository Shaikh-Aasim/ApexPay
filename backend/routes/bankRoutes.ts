import { Router } from "express";
import * as bankController from "../controllers/bankController";

const bankRoutes = Router();

bankRoutes.post("/accounts", bankController.createAccount);
bankRoutes.get("/list", bankController.getBanks);

export default bankRoutes;
