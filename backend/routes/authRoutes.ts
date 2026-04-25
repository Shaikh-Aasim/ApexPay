import { Router } from "express";
import * as authController from "../controllers/authController";

const router = Router();

// Registration Flow
router.post("/register/initiate", authController.registerInitiate);
router.post("/register/verify-otp", authController.registerVerifyOtp);
router.post("/register/set-pin", authController.registerSetPin);

// Login Flow
router.post("/login/initiate", authController.loginInitiate);
router.post("/login/verify-otp", authController.loginVerifyOtp);
router.post("/login/verify-pin", authController.loginVerifyPin);

export default router;
