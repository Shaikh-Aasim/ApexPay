export type InitiateRequest = {
  idempotencyKey?: string;
  senderVpa: string;
  receiverVpa: string;
  amount: number;
  deviceId: string;
  location: string;
};

export type InitiateResponse = {
  txnId: string;
  status: "REQUESTED" | "HOLD" | "APPROVED" | "COMPLETED" | "FAILED" | "RECOVERED";
  decision: "LOW" | "MEDIUM" | "HIGH";
  riskScore: number;
  reasons: string[];
  fraudType: string;
  holdExpiresAt?: string;
  otpRequired: boolean;
  otpDebug?: string;
};

export type ConfirmRequest = { txnId: string; otp: string; pin: string };

export type TxStatusResponse = {
  id: string;
  status: "REQUESTED" | "HOLD" | "APPROVED" | "COMPLETED" | "FAILED" | "RECOVERED";
  amount: number;
  sender_user_id: string;
  sender_account_id: string;
  receiver_user_id: string;
  receiver_account_id: string;
  risk_score: number;
  decision: "LOW" | "MEDIUM" | "HIGH";
  decision_reason: string | null;
  fraud_type: string | null;
  otp_required: boolean;
  hold_expires_at: string | null;
  failure_reason: string | null;
  retries: number;
};

export type NotificationsResponse = {
  items: Array<{ id: string; type: string; message: string; created_at: string }>;
};

export type BalanceResponse = {
  success: boolean;
  vpa: string;
  balance: number;
};

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:4000";

function extractErrorMessage(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  if (!("error" in data)) return null;
  const value = (data as Record<string, unknown>).error;
  return typeof value === "string" ? value : null;
}

function safeJsonParse(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const headers: Record<string, string> = { ...(init?.headers as Record<string, string> | undefined) };
    if (init?.body != null && headers["content-type"] == null) {
      headers["content-type"] = "application/json";
    }
    if (headers.accept == null) headers.accept = "application/json";

    const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
    const text = await res.text();
    const data = safeJsonParse(text);
    if (!res.ok) {
      const msg = extractErrorMessage(data) ?? (typeof data === "string" ? data : null) ?? `HTTP_${res.status}`;
      throw new Error(msg);
    }
    if (typeof data === "string") {
      throw new Error("BACKEND_INVALID_JSON");
    }
    return data as T;
  } catch (e) {
    if (e instanceof SyntaxError) {
      throw new Error("BACKEND_INVALID_JSON");
    }
    if (e instanceof Error) throw e;
    throw new Error("UNKNOWN_ERROR");
  }
}

export function initiatePayment(body: InitiateRequest): Promise<InitiateResponse> {
  return http<InitiateResponse>("/payment/initiate", { method: "POST", body: JSON.stringify(body) });
}

export function confirmPayment(body: ConfirmRequest): Promise<TxStatusResponse> {
  return http<TxStatusResponse>("/payment/confirm", { method: "POST", body: JSON.stringify(body) });
}

export function cancelPayment(body: { txnId: string; actorUserId?: string }): Promise<TxStatusResponse> {
  return http<TxStatusResponse>("/payment/cancel", { method: "POST", body: JSON.stringify(body) });
}

export function getBalance(vpa: string): Promise<BalanceResponse> {
  return http<BalanceResponse>(`/account/balance?vpa=${encodeURIComponent(vpa)}`);
}

export function getPaymentStatus(txnId: string): Promise<TxStatusResponse> {
  return http<TxStatusResponse>(`/payment/status?id=${encodeURIComponent(txnId)}`);
}

export function getNotifications(userId: string): Promise<NotificationsResponse> {
  return http<NotificationsResponse>(`/notifications?userId=${encodeURIComponent(userId)}`);
}

export function simulateSettlementFailure(txnId: string, mode: "AFTER_DEBIT" | "BEFORE_CREDIT"): Promise<{ ok: boolean }> {
  return http<{ ok: boolean }>("/test/settlement-failure", { method: "POST", body: JSON.stringify({ txnId, mode }) });
}
