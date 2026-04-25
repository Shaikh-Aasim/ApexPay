import { Request, Response } from "express";
import { z } from "zod";
import * as authService from "../services/authService";

const registerInitiateSchema = z.object({
  mobileNumber: z.string().regex(/^\d{10}$/, "Invalid mobile number"),
  firstName: z.string().min(1),
  lastName: z.string().min(1),
});

const verifyOtpSchema = z.object({
  mobileNumber: z.string().regex(/^\d{10}$/, "Invalid mobile number"),
  otp: z.string().length(6),
});

const setPinSchema = z.object({
  mobileNumber: z.string().regex(/^\d{10}$/, "Invalid mobile number"),
  firstName: z.string().min(1),
  lastName: z.string().min(1),
  pin: z.string().regex(/^\d{4,6}$/, "PIN must be 4 or 6 digits"),
  bankAccountId: z.string().uuid(),
});

const loginInitiateSchema = z.object({
  mobileNumber: z.string().regex(/^\d{10}$/, "Invalid mobile number"),
});

const verifyPinSchema = z.object({
  mobileNumber: z.string().regex(/^\d{10}$/, "Invalid mobile number"),
  pin: z.string().regex(/^\d{4,6}$/, "PIN must be 4 or 6 digits"),
});

export async function registerInitiate(req: Request, res: Response) {
  try {
    const data = registerInitiateSchema.parse(req.body);
    const result = await authService.initiateRegistration(data);
    res.json({ ok: true, ...result });
  } catch (e) {
    handleError(res, e);
  }
}

export async function registerVerifyOtp(req: Request, res: Response) {
  try {
    const data = verifyOtpSchema.parse(req.body);
    const result = await authService.verifyRegistrationOtp({ mobile: data.mobileNumber, otp: data.otp });
    res.json(result);
  } catch (e) {
    handleError(res, e);
  }
}

export async function registerSetPin(req: Request, res: Response) {
  try {
    const data = setPinSchema.parse(req.body);
    const result = await authService.setPinAndCompleteRegistration(data);
    res.json({ ok: true, ...result });
  } catch (e) {
    handleError(res, e);
  }
}

export async function loginInitiate(req: Request, res: Response) {
  try {
    const data = loginInitiateSchema.parse(req.body);
    const result = await authService.initiateLogin(data.mobileNumber);
    res.json({ ok: true, ...result });
  } catch (e) {
    handleError(res, e);
  }
}

export async function loginVerifyOtp(req: Request, res: Response) {
  try {
    const data = verifyOtpSchema.parse(req.body);
    const result = await authService.verifyLoginOtp({ mobile: data.mobileNumber, otp: data.otp });
    res.json(result);
  } catch (e) {
    handleError(res, e);
  }
}

export async function loginVerifyPin(req: Request, res: Response) {
  try {
    const data = verifyPinSchema.parse(req.body);
    const result = await authService.verifyPinAndLogin({ mobile: data.mobileNumber, pin: data.pin });
    res.json({ ok: true, ...result });
  } catch (e) {
    handleError(res, e);
  }
}

function handleError(res: Response, e: any) {
  console.error("Auth Error:", e);
  if (e instanceof z.ZodError) {
    return res.status(400).json({ ok: false, error: "VALIDATION_ERROR", details: e.issues });
  }
  const message = e instanceof Error ? e.message : "UNKNOWN_ERROR";
  res.status(400).json({ ok: false, error: message });
}
