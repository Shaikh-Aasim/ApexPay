export type InitiateRequest = {
  idempotencyKey?: string;
  senderVpa: string;
  receiverVpa?: string;
  receiverMobile?: string;
  amount: number;
  deviceId: string;
  location: string;
  pin?: string;
  paymentNote?: string;
};

export type TransactionHistoryItem = {
  id: string;
  amount: number;
  status: string;
  timestamp: string;
  paymentNote?: string;
  type: "DEBIT" | "CREDIT";
  name: string;
  vpa: string;
  accountNumber: string;
  bankName: string;
  senderName: string;
  senderVpa: string;
  senderAccountNumber: string;
  senderBankName: string;
  receiverName: string;
  receiverVpa: string;
  receiverAccountNumber: string;
  receiverBankName: string;
};

export type TransactionHistoryResponse = {
  items: TransactionHistoryItem[];
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

// Auth Types
export type AuthUser = {
  id: string;
  firstName: string;
  lastName: string;
  mobile: string;
  vpa?: string;
};

export type LoginResponse = {
  ok: boolean;
  token: string;
  user: AuthUser;
};

export type RegisterInitiateResponse = {
  ok: boolean;
  otpDebug?: string;
  availableBanks: Array<{ id: string; bankName: string; accountNumber: string }>;
};

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:4000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("apexpay_token");
}

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

    // Inject JWT Token
    const token = getAuthToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

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

// Auth APIs
export function loginInitiate(mobileNumber: string): Promise<{ ok: boolean; otpDebug?: string }> {
  return http<{ ok: boolean; otpDebug?: string }>("/api/auth/login/initiate", {
    method: "POST",
    body: JSON.stringify({ mobileNumber }),
  });
}

export function loginVerifyOtp(mobileNumber: string, otp: string): Promise<{ ok: boolean }> {
  return http<{ ok: boolean }>("/api/auth/login/verify-otp", {
    method: "POST",
    body: JSON.stringify({ mobileNumber, otp }),
  });
}

export function loginVerifyPin(mobileNumber: string, pin: string): Promise<LoginResponse> {
  return http<LoginResponse>("/api/auth/login/verify-pin", {
    method: "POST",
    body: JSON.stringify({ mobileNumber, pin }),
  });
}

export function registerInitiate(body: { mobileNumber: string; firstName: string; lastName: string }): Promise<RegisterInitiateResponse> {
  return http<RegisterInitiateResponse>("/api/auth/register/initiate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function registerVerifyOtp(mobileNumber: string, otp: string): Promise<{ ok: boolean }> {
  return http<{ ok: boolean }>("/api/auth/register/verify-otp", {
    method: "POST",
    body: JSON.stringify({ mobileNumber, otp }),
  });
}

export function registerSetPin(body: {
  mobileNumber: string;
  firstName: string;
  lastName: string;
  pin: string;
  bankAccountId: string;
}): Promise<{ ok: boolean; userId: string; vpa: string }> {
  return http<{ ok: boolean; userId: string; vpa: string }>("/api/auth/register/set-pin", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// Bank Registry APIs
export function createBankRegistryAccount(body: {
  firstName: string;
  lastName: string;
  aadharNumber: string;
  mobileNumber: string;
  accountNumber: string;
  bankId: string;
  ifscCode: string;
  balance: number;
}): Promise<{ ok: boolean; accountId: string }> {
  return http<{ ok: boolean; accountId: string }>("/api/bank/accounts", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getBankList(): Promise<{ ok: boolean; banks: Array<{ id: string; name: string }> }> {
  return http<{ ok: boolean; banks: Array<{ id: string; name: string }> }>("/api/bank/list", {
    method: "GET",
  });
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

export function getBalance(vpa?: string, pin?: string): Promise<BalanceResponse> {
  let url = "/account/balance";
  const params = new URLSearchParams();
  if (vpa) params.append("vpa", vpa);
  if (pin) params.append("pin", pin);
  if (params.toString()) url += `?${params.toString()}`;
  return http<BalanceResponse>(url);
}

export function resolveReceiver(vpa?: string, mobile?: string): Promise<{ success: boolean; name: string; vpa: string }> {
  let url = "/account/resolve";
  const params = new URLSearchParams();
  if (vpa) params.append("vpa", vpa);
  if (mobile) params.append("mobile", mobile);
  if (params.toString()) url += `?${params.toString()}`;
  return http<{ success: boolean; name: string; vpa: string }>(url);
}

export function getPaymentStatus(txnId: string): Promise<TxStatusResponse> {
  return http<TxStatusResponse>(`/payment/status?id=${encodeURIComponent(txnId)}`);
}

export function getNotifications(userId: string): Promise<NotificationsResponse> {
  return http<NotificationsResponse>(`/notifications?userId=${encodeURIComponent(userId)}`);
}

export function getTransactionHistory(): Promise<TransactionHistoryResponse> {
  return http<TransactionHistoryResponse>("/payment/history");
}

export function simulateSettlementFailure(txnId: string, mode: "AFTER_DEBIT" | "BEFORE_CREDIT"): Promise<{ ok: boolean }> {
  return http<{ ok: boolean }>("/test/settlement-failure", { method: "POST", body: JSON.stringify({ txnId, mode }) });
}
