import { NextFunction, Request, Response } from "express";
import jwt from "jsonwebtoken";

const JWT_SECRET = process.env.JWT_SECRET || "apexpay_super_secret_key";

export interface AuthRequest extends Request {
  user?: {
    userId: string;
    mobile: string;
    name: string;
  };
}

export function authMiddleware(req: AuthRequest, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return res.status(401).json({ ok: false, error: "UNAUTHORIZED", message: "Missing or invalid token" });
  }

  const token = authHeader.split(" ")[1];
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as {
      userId: string;
      mobile: string;
      name: string;
    };
    req.user = decoded;
    next();
  } catch (e) {
    console.error("JWT Verify Error:", e);
    return res.status(401).json({ ok: false, error: "INVALID_TOKEN", message: "Token is expired or invalid" });
  }
}
