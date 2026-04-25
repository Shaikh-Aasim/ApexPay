import bcrypt from "bcrypt";
import jwt from "jsonwebtoken";
import { env } from "../config/env";
import { pool } from "../utils/db";
import { redis } from "../utils/redis";
import { findBankAccountsByMobile, getBankAccountById } from "./bankService";
import { checkOtpVerified, clearOtpVerified, issueMobileOtp, verifyMobileOtp } from "./otpService";

const JWT_SECRET = process.env.JWT_SECRET || "apexpay_super_secret_key";
const SALT_ROUNDS = 10;

export async function initiateRegistration(args: {
  mobileNumber: string;
  firstName: string;
  lastName: string;
}) {
  // 1. Check if user already exists
  const existingUser = await pool.query("select id from users where mobile_number = $1", [args.mobileNumber]);
  if (existingUser.rows[0]) throw new Error("USER_ALREADY_EXISTS");

  // 2. Check if mobile number exists in Central Bank Database and matches details
  const bankAccounts = await findBankAccountsByMobile(args.mobileNumber);
  if (bankAccounts.length === 0) throw new Error("NUMBER_NOT_LINKED_TO_BANK");

  // Optional: Verify if the name matches at least one bank account record
  const nameMatch = bankAccounts.some(ba => 
    ba.firstName?.trim().toLowerCase() === args.firstName.trim().toLowerCase() && 
    ba.lastName?.trim().toLowerCase() === args.lastName.trim().toLowerCase()
  );
  
  // For better UX in simulation, we can just log if it doesn't match or be strict
  if (!nameMatch) {
    console.warn(`Registration name mismatch for ${args.mobileNumber}: Input="${args.firstName} ${args.lastName}", BankRecords=${JSON.stringify(bankAccounts.map(b => `${b.firstName} ${b.lastName}`))}`);
    // If you want to be strict:
    // throw new Error("DETAILS_MISMATCH_WITH_BANK_RECORD");
  }

  // 3. Send OTP
  const otp = await issueMobileOtp({ mobile: args.mobileNumber, ttlSeconds: 300, type: "REGISTER" });

  return { 
    otpDebug: otp, 
    availableBanks: bankAccounts.map(ba => ({ 
      id: ba.id, 
      bankName: ba.bankName, 
      accountNumber: ba.accountNumber 
    })) 
  };
}

export async function verifyRegistrationOtp(args: { mobile: string; otp: string }) {
  await verifyMobileOtp({ mobile: args.mobile, otp: args.otp, maxAttempts: 3, type: "REGISTER" });
  return { ok: true };
}

export async function setPinAndCompleteRegistration(args: {
  mobileNumber: string;
  firstName: string;
  lastName: string;
  pin: string;
  bankAccountId: string;
}) {
  // 1. Ensure OTP was verified
  const isVerified = await checkOtpVerified(args.mobileNumber);
  console.log(`[AUTH DEBUG] isVerified for ${args.mobileNumber}: ${isVerified}`);
  if (!isVerified) throw new Error("OTP_NOT_VERIFIED");

  // 2. Get bank account details
  const bankAccount = await getBankAccountById(args.bankAccountId);
  if (!bankAccount || bankAccount.mobileNumber !== args.mobileNumber) {
    throw new Error("INVALID_BANK_ACCOUNT");
  }

  const client = await pool.connect();
  try {
    await client.query("begin");

    // 3. Hash PIN
    const pinHash = await bcrypt.hash(args.pin, SALT_ROUNDS);

    // 4. Create User
    const fullName = `${args.firstName} ${args.lastName}`;
    const userResult = await client.query(
      `insert into users (first_name, last_name, full_name, mobile_number, pin_hash)
       values ($1, $2, $3, $4, $5)
       returning id::text as id`,
      [args.firstName, args.lastName, fullName, args.mobileNumber, pinHash]
    );
    const userId = userResult.rows[0].id;

    // 5. Link Bank Account internally
    await client.query(
      `insert into accounts (user_id, bank_id, balance)
       values ($1, $2, $3)`,
      [userId, bankAccount.bankId, bankAccount.balance]
    );

    // 6. Create a default VPA
    const vpa = `${args.firstName.toLowerCase()}${args.mobileNumber.slice(-4)}@apex`;
    await client.query(
      `insert into vpas (user_id, bank_id, account_id, vpa)
       select $1, $2, a.id, $3
       from accounts a 
       where a.user_id = $1 and a.bank_id = $2`,
      [userId, bankAccount.bankId, vpa]
    );

    await client.query("commit");
    await clearOtpVerified(args.mobileNumber);

    return { userId, vpa };
  } catch (e) {
    await client.query("rollback");
    throw e;
  } finally {
    client.release();
  }
}

export async function initiateLogin(mobileNumber: string) {
  const user = await pool.query("select id from users where mobile_number = $1", [mobileNumber]);
  if (!user.rows[0]) throw new Error("USER_NOT_FOUND");

  const otp = await issueMobileOtp({ mobile: mobileNumber, ttlSeconds: 300, type: "LOGIN" });
  return { otpDebug: otp };
}

export async function verifyLoginOtp(args: { mobile: string; otp: string }) {
  await verifyMobileOtp({ mobile: args.mobile, otp: args.otp, maxAttempts: 3, type: "LOGIN" });
  
  // Store a temporary flag that OTP is verified for this login attempt
  await redis.set(`login:otp_verified:${args.mobile}`, "true", { ex: 300 });
  return { ok: true };
}

export async function verifyPinAndLogin(args: { mobile: string; pin: string }) {
  // 1. Check if OTP was verified
  const otpVerified = await redis.get(`login:otp_verified:${args.mobile}`);
  console.log(`[AUTH DEBUG] Login OTP verification check for ${args.mobile}:`, otpVerified, "Type:", typeof otpVerified);
  
  if (otpVerified !== "true" && otpVerified !== true) throw new Error("OTP_NOT_VERIFIED");

  // 2. Check User and PIN
  const userResult = await pool.query(
    "select id::text as id, first_name, last_name, pin_hash from users where mobile_number = $1",
    [args.mobile]
  );
  const user = userResult.rows[0];
  if (!user) throw new Error("USER_NOT_FOUND");

  const pinOk = await bcrypt.compare(args.pin, user.pin_hash);
  if (!pinOk) throw new Error("INVALID_PIN");

  // 3. Generate JWT
  const token = jwt.sign(
    { 
      userId: user.id, 
      mobile: args.mobile,
      name: `${user.first_name} ${user.last_name}` 
    },
    JWT_SECRET,
    { expiresIn: "24h" }
  );

  // 4. Get User's VPA
  const vpaResult = await pool.query("select vpa from vpas where user_id = $1 limit 1", [user.id]);
  const vpa = vpaResult.rows[0]?.vpa || `${user.first_name.toLowerCase()}${args.mobile.slice(-4)}@apex`;

  await redis.del(`login:otp_verified:${args.mobile}`);
  
  return { 
    token, 
    user: { 
      id: user.id, 
      firstName: user.first_name, 
      lastName: user.last_name, 
      mobile: args.mobile,
      vpa: vpa
    } 
  };
}
