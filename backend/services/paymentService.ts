import bcrypt from "bcrypt";
import crypto from "crypto";
import { env } from "../config/env";
import { pool } from "../utils/db";
import { acquireLock, releaseLock } from "../utils/redis";
import { auditLog } from "./auditService";
import { computeDeviceChange, computeLocationAnomaly, getTxnCount24h, getUserAmountStats30d, updateBehaviorAnchors } from "./behaviorService";
import { getCrashPoint, getDelayMs } from "./chaosService";
import { predictRisk, RiskDecision, RiskRequest } from "./mlService";
import { notifyUser } from "./notificationService";
import { issueOtp, verifyOtp } from "./otpService";
import { getReceiverRisk } from "./receiverRiskService";
import { releaseReservedFunds, reserveFunds } from "./reserveService";

type TxStatus =
  | "REQUESTED"
  | "HOLD"
  | "APPROVED"
  | "COMPLETED"
  | "FAILED"
  | "RECOVERED";

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function resolveVpa(vpa: string): Promise<{ userId: string; accountId: string; balance: number }> {
  const r = await pool.query(
    `select v.user_id::text as user_id, v.account_id::text as account_id, a.balance::float as balance
     from vpas v
     join accounts a on a.id = v.account_id
     where v.vpa = $1`,
    [vpa]
  );
  if (!r.rows[0]) throw new Error("VPA_NOT_FOUND");
  return { userId: String(r.rows[0].user_id), accountId: String(r.rows[0].account_id), balance: Number(r.rows[0].balance) };
}

async function resolveUser(userId: string): Promise<{ userId: string; accountId: string; balance: number; vpa: string }> {
  const r = await pool.query(
    `select v.vpa, v.user_id::text as user_id, v.account_id::text as account_id, a.balance::float as balance
     from vpas v
     join accounts a on a.id = v.account_id
     where v.user_id = $1
     order by a.balance desc
     limit 1`,
    [userId]
  );
  if (!r.rows[0]) throw new Error("USER_ACCOUNT_NOT_FOUND");
  return { 
    userId: String(r.rows[0].user_id), 
    accountId: String(r.rows[0].account_id), 
    balance: Number(r.rows[0].balance),
    vpa: String(r.rows[0].vpa)
  };
}

async function resolveMobile(mobile: string): Promise<{ userId: string; accountId: string; balance: number; vpa: string }> {
  const r = await pool.query(
    `select v.vpa, v.user_id::text as user_id, v.account_id::text as account_id, a.balance::float as balance
     from users u
     join vpas v on v.user_id = u.id
     join accounts a on a.id = v.account_id
     where u.mobile_number = $1
     order by a.balance desc
     limit 1`,
    [mobile]
  );
  if (!r.rows[0]) throw new Error("MOBILE_NOT_FOUND_IN_APEXPAY");
  return { 
    userId: String(r.rows[0].user_id), 
    accountId: String(r.rows[0].account_id), 
    balance: Number(r.rows[0].balance),
    vpa: String(r.rows[0].vpa)
  };
}

export async function initiatePayment(args: {
  idempotencyKey?: string;
  senderVpa?: string;
  senderUserId?: string;
  receiverVpa?: string;
  receiverMobile?: string;
  amount: number;
  deviceId: string;
  location: string;
  pin?: string;
  paymentNote?: string;
}): Promise<{ txnId: string; status: TxStatus; decision: RiskDecision; riskScore: number; reasons: string[]; fraudType: string; holdExpiresAt?: string; otpRequired: boolean; otpDebug?: string }> {
  // Verify PIN if provided
  if (args.pin && args.senderUserId) {
    const userRes = await pool.query("select pin_hash from users where id = $1", [args.senderUserId]);
    if (userRes.rows[0]) {
      const pinOk = await bcrypt.compare(args.pin, userRes.rows[0].pin_hash);
      if (!pinOk) throw new Error("INVALID_PIN");
    }
  }

  if (args.idempotencyKey) {
    const existing = await pool.query(`select id::text as id from transactions where idempotency_key = $1`, [args.idempotencyKey]);
    if (existing.rows[0]) {
      const s = await getPaymentStatus(String(existing.rows[0].id));
      return {
        txnId: s.id,
        status: s.status,
        decision: s.decision,
        riskScore: s.risk_score,
        reasons: s.decision_reason ? s.decision_reason.split(" | ") : [],
        fraudType: s.fraud_type ?? "UNKNOWN",
        holdExpiresAt: s.hold_expires_at ?? undefined,
        otpRequired: Boolean(s.otp_required),
      };
    }
  }

  const [sender, receiver] = await Promise.all([
    args.senderUserId ? resolveUser(args.senderUserId) : resolveVpa(args.senderVpa!),
    args.receiverVpa ? resolveVpa(args.receiverVpa) : resolveMobile(args.receiverMobile!),
  ]);

  const finalSenderVpa = args.senderUserId ? (sender as any).vpa : args.senderVpa!;
  const finalReceiverVpa = args.receiverVpa || (receiver as any).vpa;
  if (sender.accountId === receiver.accountId) throw new Error("SAME_ACCOUNT");

  const [txnCount24h, stats30d, deviceChange, locationAnomaly, receiverRisk] = await Promise.all([
    getTxnCount24h(sender.userId),
    getUserAmountStats30d(sender.userId),
    computeDeviceChange(sender.userId, args.deviceId),
    computeLocationAnomaly(sender.userId, args.location),
    getReceiverRisk(receiver.userId),
  ]);

  const avg = stats30d.avg > 0 ? stats30d.avg : args.amount;
  const std = stats30d.std > 0 ? stats30d.std : Math.max(1, avg * 0.2);
  const amountZ = (args.amount - avg) / std;
  // 🔥 NEW LOGIC: detect first transaction
  const totalTxnRes = await pool.query(
    `SELECT COUNT(*) FROM transactions WHERE sender_user_id = $1`,
    [sender.userId]
  );

  const totalTxnCount = parseInt(totalTxnRes.rows[0].count, 10);

  // safer version (recommended)
  const isFirstTransaction = totalTxnCount <= 1;

  // debug
  console.log("TOTAL TXN COUNT:", totalTxnCount);
  console.log("IS FIRST TRANSACTION:", isFirstTransaction);
  const riskPayload: RiskRequest = {
    amount: args.amount,
    txn_count_24h: txnCount24h,
    device_change: deviceChange,
    location_anomaly: locationAnomaly,
    receiver_suspicion_score: receiverRisk.suspicionScore,
    receiver_flagged: receiverRisk.flagged ? 1 : 0,
    user_avg_amount_30d: avg,
    user_std_amount_30d: std,
    amount_zscore: amountZ,
    is_first_transaction: isFirstTransaction,
    // account_age_hours: userAgeHours,
  };

  const ml = await predictRisk(riskPayload);
  const decision = ml.decision;
  const reasons = ml.reasons;
  const reasonText = reasons.join(" | ");

  let status: TxStatus = "REQUESTED";
  let otpRequired = false;
  let holdExpiresAt: string | null = null;
  let failureReason: string | null = null;

  if (decision === "HIGH") {
    status = "FAILED";
    failureReason = "RISK_REJECTED";
  } else if (decision === "MEDIUM") {
    status = "HOLD";
    otpRequired = true;
    holdExpiresAt = new Date(Date.now() + env.HOLD_TTL_SECONDS * 1000).toISOString();
  }

  const created = await pool.query(
    `insert into transactions(
        idempotency_key,
        sender_user_id, sender_account_id, sender_vpa,
        receiver_user_id, receiver_account_id, receiver_vpa,
        amount, status,
        risk_score, decision, decision_reason, fraud_type, model_version, risk_features,
        otp_required, hold_expires_at,
        failure_reason, payment_note
     ) values (
        $1,
        $2, $3, $4,
        $5, $6, $7,
        $8, $9,
        $10, $11, $12, $13, $14, $15::jsonb,
        $16, $17,
        $18, $19
     )
     returning id::text as id`,
    [
      args.idempotencyKey ?? null,
      sender.userId,
      sender.accountId,
      finalSenderVpa,
      receiver.userId,
      receiver.accountId,
      finalReceiverVpa,
      args.amount,
      status,
      ml.risk_score,
      decision,
      reasonText,
      ml.fraud_type,
      ml.model_version,
      JSON.stringify(riskPayload),
      otpRequired,
      holdExpiresAt,
      failureReason,
      args.paymentNote ?? null,
    ]
  );
  const txnId = String(created.rows[0].id);

  await pool.query(
    `insert into risk_scores(txn_id, risk_score, decision, decision_reason, fraud_type, model_version, risk_features)
     values ($1, $2, $3, $4, $5, $6, $7::jsonb)`,
    [txnId, ml.risk_score, decision, reasonText, ml.fraud_type, ml.model_version, JSON.stringify(riskPayload)]
  );

  await auditLog({
    txnId,
    actorUserId: sender.userId,
    action: "PAYMENT_INITIATED",
    payload: { senderVpa: finalSenderVpa, receiverVpa: finalReceiverVpa, amount: args.amount, decision, risk_score: ml.risk_score },
  });

  await updateBehaviorAnchors({ userId: sender.userId, deviceId: args.deviceId, location: args.location });

  if (decision === "HIGH") {
    await notifyUser({ userId: sender.userId, type: "RISK_REJECTED", message: `Rejected as high-risk: ₹${args.amount}` });
    return { txnId, status, decision, riskScore: ml.risk_score, reasons, fraudType: ml.fraud_type, otpRequired: false };
  }

  if (decision === "MEDIUM") {
    await reserveFunds({ accountId: sender.accountId, amount: args.amount, balanceLimit: sender.balance });
    const otp = await issueOtp({ txnId, ttlSeconds: env.HOLD_TTL_SECONDS });
    await notifyUser({ userId: sender.userId, type: "HOLD_TRIGGERED", message: `HOLD: confirm OTP to approve ₹${args.amount}` });
    return {
      txnId,
      status,
      decision,
      riskScore: ml.risk_score,
      reasons,
      fraudType: ml.fraud_type,
      holdExpiresAt: holdExpiresAt ?? undefined,
      otpRequired: true,
      otpDebug: otp,
    };
  }

  await pool.query(`update transactions set status = 'APPROVED', updated_at = now() where id = $1`, [txnId]);
  await auditLog({ txnId, actorUserId: sender.userId, action: "PAYMENT_APPROVED_AUTO", payload: { decision, risk_score: ml.risk_score } });
  await processTransaction({ txnId, asRecovery: false });
  const s = await getPaymentStatus(txnId);
  return {
    txnId,
    status: s.status,
    decision,
    riskScore: ml.risk_score,
    reasons,
    fraudType: ml.fraud_type,
    otpRequired: false,
  };
}

export async function confirmPayment(args: { txnId: string; otp: string; pin: string }): Promise<void> {
  const s = await getPaymentStatus(args.txnId);
  if (s.status !== "HOLD") throw new Error("NOT_HOLD");
  if (!s.hold_expires_at) throw new Error("HOLD_MISSING_EXPIRES");
  if (new Date(s.hold_expires_at).getTime() < Date.now()) throw new Error("HOLD_EXPIRED");
  if (args.pin.trim() !== "1234") throw new Error("PIN_INVALID");

  await verifyOtp({ txnId: args.txnId, otp: args.otp, maxAttempts: 5 });

  await pool.query(`update transactions set status = 'APPROVED', confirmed_at = now(), updated_at = now() where id = $1`, [args.txnId]);
  await auditLog({ txnId: args.txnId, actorUserId: s.sender_user_id, action: "HOLD_CONFIRMED", payload: { mfa: "otp+pin" } });
  await processTransaction({ txnId: args.txnId, asRecovery: false });
}

export async function cancelPayment(args: { txnId: string; actorUserId?: string }): Promise<void> {
  const s = await getPaymentStatus(args.txnId);
  if (s.status !== "HOLD") throw new Error("ONLY_HOLD_CAN_CANCEL");
  await pool.query(
    `update transactions set status = 'FAILED', failure_reason = 'CANCELED_BY_USER', updated_at = now() where id = $1`,
    [args.txnId]
  );
  await releaseReservedFunds({ accountId: s.sender_account_id, amount: s.amount });
  await auditLog({ txnId: args.txnId, actorUserId: args.actorUserId ?? s.sender_user_id, action: "HOLD_CANCELED" });
  await notifyUser({ userId: s.sender_user_id, type: "PAYMENT_STATUS", message: `Payment canceled: ₹${s.amount}` });
}

export async function getPaymentStatus(txnId: string): Promise<{
  id: string;
  status: TxStatus;
  amount: number;
  sender_user_id: string;
  sender_account_id: string;
  receiver_user_id: string;
  receiver_account_id: string;
  risk_score: number;
  decision: RiskDecision;
  decision_reason: string | null;
  fraud_type: string | null;
  otp_required: boolean;
  hold_expires_at: string | null;
  failure_reason: string | null;
  retries: number;
}> {
  const r = await pool.query(
    `select
        id::text,
        status::text,
        amount::float as amount,
        sender_user_id::text,
        sender_account_id::text,
        receiver_user_id::text,
        receiver_account_id::text,
        coalesce(risk_score, 0)::float as risk_score,
        coalesce(decision, 'LOW')::text as decision,
        decision_reason,
        fraud_type::text,
        otp_required,
        hold_expires_at::text,
        failure_reason,
        retries
     from transactions
     where id = $1`,
    [txnId]
  );
  if (!r.rows[0]) throw new Error("TXN_NOT_FOUND");
  const row = r.rows[0] as any;
  return {
    id: String(row.id),
    status: String(row.status) as TxStatus,
    amount: Number(row.amount),
    sender_user_id: String(row.sender_user_id),
    sender_account_id: String(row.sender_account_id),
    receiver_user_id: String(row.receiver_user_id),
    receiver_account_id: String(row.receiver_account_id),
    risk_score: Number(row.risk_score),
    decision: String(row.decision) as RiskDecision,
    decision_reason: row.decision_reason ? String(row.decision_reason) : null,
    fraud_type: row.fraud_type ? String(row.fraud_type) : null,
    otp_required: Boolean(row.otp_required),
    hold_expires_at: row.hold_expires_at ? String(row.hold_expires_at) : null,
    failure_reason: row.failure_reason ? String(row.failure_reason) : null,
    retries: Number(row.retries ?? 0),
  };
}

export async function getTransactionHistory(userId: string) {
  const r = await pool.query(
    `select
        t.id::text,
        t.amount::float as amount,
        t.status::text,
        t.sender_user_id::text,
        t.sender_vpa,
        t.receiver_user_id::text,
        t.receiver_vpa,
        t.payment_note,
        t.created_at::text,
        
        -- Sender Info
        us.first_name || ' ' || us.last_name as sender_name,
        bas.account_number as sender_account_number,
        bs.name as sender_bank_name,
        
        -- Receiver Info
        ur.first_name || ' ' || ur.last_name as receiver_name,
        bar.account_number as receiver_account_number,
        br.name as receiver_bank_name
        
     from transactions t
     join users us on us.id = t.sender_user_id
     join accounts as_ on as_.id = t.sender_account_id
     join bank_accounts bas on bas.mobile_number = us.mobile_number and bas.bank_id = as_.bank_id
     join banks bs on bs.id = as_.bank_id
     
     join users ur on ur.id = t.receiver_user_id
     join accounts ar on ar.id = t.receiver_account_id
     join bank_accounts bar on bar.mobile_number = ur.mobile_number and bar.bank_id = ar.bank_id
     join banks br on br.id = ar.bank_id
     
     where t.sender_user_id = $1 or t.receiver_user_id = $1
     order by t.created_at desc`,
    [userId]
  );

  return r.rows.map((row: any) => {
    const isSender = row.sender_user_id === userId;
    return {
      id: row.id,
      amount: row.amount,
      status: row.status,
      timestamp: row.created_at,
      paymentNote: row.payment_note,
      type: isSender ? "DEBIT" : "CREDIT",
      
      // Counterparty info
      name: isSender ? row.receiver_name : row.sender_name,
      vpa: isSender ? row.receiver_vpa : row.sender_vpa,
      accountNumber: isSender ? row.receiver_account_number : row.sender_account_number,
      bankName: isSender ? row.receiver_bank_name : row.sender_bank_name,
      
      // Full details for receipt
      senderName: row.sender_name,
      senderVpa: row.sender_vpa,
      senderAccountNumber: row.sender_account_number,
      senderBankName: row.sender_bank_name,
      
      receiverName: row.receiver_name,
      receiverVpa: row.receiver_vpa,
      receiverAccountNumber: row.receiver_account_number,
      receiverBankName: row.receiver_bank_name
    };
  });
}

export async function processTransaction(args: { txnId: string; asRecovery: boolean }): Promise<void> {
  const s = await getPaymentStatus(args.txnId);
  if (s.status !== "APPROVED") throw new Error("NOT_APPROVED");

  const lockKey = `user_lock:${s.sender_user_id}`;
  const lockValue = crypto.randomBytes(16).toString("hex");
  const ok = await acquireLock({ key: lockKey, value: lockValue, ttlMs: env.LOCK_TTL_MS });
  if (!ok) throw new Error("CONCURRENCY_LOCKED");

  const client = await pool.connect();
  try {
    const delay = await getDelayMs();
    if (delay > 0) await sleep(delay);

    const crash = await getCrashPoint();

    // --- PHASE 1: DEBIT ---
    // If not already debited in a previous failed attempt
    if (s.failure_reason !== "SENDER_DEBITED") {
      await client.query("begin");
      
      const senderRow = await client.query(`select balance::float as balance from accounts where id = $1 for update`, [
        s.sender_account_id,
      ]);
      if (!senderRow.rows[0]) throw new Error("ACCOUNT_NOT_FOUND");
      const senderBalance = Number(senderRow.rows[0].balance);
      if (senderBalance < s.amount) throw new Error("INSUFFICIENT_FUNDS_DB");

      if (crash === "BEFORE_DEBIT") throw new Error("SIMULATED_CRASH");

      await client.query(`update accounts set balance = balance - $2 where id = $1`, [s.sender_account_id, s.amount]);
      
      // Update txn to mark debit done
      await client.query(
        `update transactions set failure_reason = 'SENDER_DEBITED', updated_at = now() where id = $1`,
        [s.id]
      );
      
      await client.query("commit");
      
      await auditLog({ txnId: s.id, actorUserId: s.sender_user_id, action: "SENDER_DEBIT_SUCCESS" });
      await notifyUser({ userId: s.sender_user_id, type: "PAYMENT_DEBITED", message: `₹${s.amount} debited from your account` });
    }

    // Simulate crash AFTER_DEBIT or BEFORE_CREDIT
    if (crash === "AFTER_DEBIT" || crash === "BEFORE_CREDIT") throw new Error("SIMULATED_CRASH");

    // --- PHASE 2: CREDIT ---
    await client.query("begin");
    
    const receiverRow = await client.query(`select balance::float as balance from accounts where id = $1 for update`, [
      s.receiver_account_id,
    ]);
    if (!receiverRow.rows[0]) throw new Error("RECEIVER_ACCOUNT_NOT_FOUND");

    await client.query(`update accounts set balance = balance + $2 where id = $1`, [s.receiver_account_id, s.amount]);

    await client.query(
      `update transactions
       set status = $2, completed_at = now(), updated_at = now(), failure_reason = null
       where id = $1`,
      [s.id, args.asRecovery ? "RECOVERED" : "COMPLETED"]
    );

    await client.query("commit");

    await releaseReservedFunds({ accountId: s.sender_account_id, amount: s.amount });
    await auditLog({
      txnId: s.id,
      actorUserId: s.sender_user_id,
      action: args.asRecovery ? "PAYMENT_RECOVERED" : "PAYMENT_COMPLETED",
    });
    await Promise.all([
      notifyUser({ userId: s.sender_user_id, type: "PAYMENT_STATUS", message: `Payment ${args.asRecovery ? "recovered" : "completed"}: ₹${s.amount}` }),
      notifyUser({ userId: s.receiver_user_id, type: "PAYMENT_RECEIVED", message: `Received ₹${s.amount} from User ${s.sender_user_id.slice(0, 4)}` }),
    ]);
  } catch (e) {
    try {
      await client.query("rollback");
    } catch {
    }
    const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
    
    // Increment retries but KEEP status as APPROVED so worker picks it up
    await pool.query(
      `update transactions set retries = retries + 1, updated_at = now() where id = $1`,
      [s.id]
    );

    await auditLog({ txnId: s.id, actorUserId: s.sender_user_id, action: "PAYMENT_FAILED_ATTEMPT", payload: { error: msg, attempt: s.retries + 1 } });
    throw e;
  } finally {
    client.release();
    await releaseLock({ key: lockKey, value: lockValue });
  }
}

export async function rollbackTransaction(args: { txnId: string }): Promise<void> {
  const s = await getPaymentStatus(args.txnId);
  if (s.status !== "APPROVED") throw new Error("CANNOT_ROLLBACK_NON_APPROVED");

  const client = await pool.connect();
  try {
    await client.query("begin");

    // Ensure we don't rollback multiple times
    const check = await client.query(`select status from transactions where id = $1 for update`, [s.id]);
    if (check.rows[0].status !== "APPROVED") {
      await client.query("rollback");
      return;
    }

    // 1. Credit back sender IF they were debited
    if (s.failure_reason === "SENDER_DEBITED") {
      await client.query(`update accounts set balance = balance + $2 where id = $1`, [s.sender_account_id, s.amount]);
    }

    // 2. Mark txn as FAILED
    await client.query(
      `update transactions 
       set status = 'FAILED', failure_reason = 'ROLLBACK_AFTER_MAX_RETRIES', updated_at = now() 
       where id = $1`,
      [s.id]
    );

    await client.query("commit");

    await releaseReservedFunds({ accountId: s.sender_account_id, amount: s.amount });
    await auditLog({ txnId: s.id, actorUserId: s.sender_user_id, action: "PAYMENT_ROLLED_BACK" });
    await notifyUser({ 
      userId: s.sender_user_id, 
      type: "PAYMENT_REFUNDED", 
      message: `Transaction failed. ₹${s.amount} refunded to your account` 
    });
  } catch (e) {
    await client.query("rollback");
    throw e;
  } finally {
    client.release();
  }
}

export async function expireHolds(): Promise<number> {
  const r = await pool.query(
    `select id::text as id
     from transactions
     where status = 'HOLD'
       and hold_expires_at is not null
       and hold_expires_at < now()
     limit 50`
  );
  const ids = r.rows.map((x: any) => String(x.id));
  if (ids.length === 0) return 0;
  for (const id of ids) {
    const s = await getPaymentStatus(id);
    await pool.query(`update transactions set status = 'FAILED', failure_reason = 'HOLD_EXPIRED', updated_at = now() where id = $1`, [id]);
    await releaseReservedFunds({ accountId: s.sender_account_id, amount: s.amount });
    await auditLog({ txnId: id, actorUserId: s.sender_user_id, action: "HOLD_EXPIRED_AUTO" });
    await notifyUser({ userId: s.sender_user_id, type: "PAYMENT_STATUS", message: `HOLD expired: ₹${s.amount}` });
  }
  return ids.length;
}

export async function recoverStuckApproved(): Promise<number> {
  const r = await pool.query(
    `select id::text as id, retries
     from transactions
     where status = 'APPROVED'
       and updated_at < now() - interval '5 seconds'
     order by updated_at asc
     limit 25`
  );
  const rows = r.rows;
  for (const row of rows) {
    const id = String(row.id);
    const retries = Number(row.retries);
    try {
      if (retries >= 3) {
        console.log(`Max retries reached for ${id}, rolling back...`);
        await rollbackTransaction({ txnId: id });
      } else {
        console.log(`Retrying settlement for ${id}, attempt ${retries + 1}`);
        await processTransaction({ txnId: id, asRecovery: true });
      }
    } catch (e) {
      console.error(`Recovery failed for ${id}:`, e);
    }
  }
  return rows.length;
}
