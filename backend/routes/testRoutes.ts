import { Router } from "express";
import * as testController from "../controllers/testController";

export const testRoutes = Router();

testRoutes.post("/delay", testController.delay);
testRoutes.post("/crash", testController.crash);
testRoutes.post("/settlement-failure", testController.simulateSettlementFailure);

