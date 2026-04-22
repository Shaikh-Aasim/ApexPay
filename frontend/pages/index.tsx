import { useEffect, useMemo, useState } from "react";
import {
  cancelPayment,
  confirmPayment,
  getNotifications,
  getPaymentStatus,
  initiatePayment,
  type InitiateResponse,
  type TxStatusResponse,
} from "../services/backend";

export default function Home() {
  const [senderVpa, setSenderVpa] = useState("aarav@apex");
  const [receiverVpa, setReceiverVpa] = useState("isha@neo");
  const [amount, setAmount] = useState("1000");
  const [deviceId, setDeviceId] = useState("device_web_1");
  const [location, setLocation] = useState("IN-MH");
  const [idempotencyKey, setIdempotencyKey] = useState("");

  const [init, setInit] = useState<InitiateResponse | null>(null);
  const [status, setStatus] = useState<TxStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [otp, setOtp] = useState("");
  const [pin, setPin] = useState("");
  const [holdRemainingMs, setHoldRemainingMs] = useState(0);

  const [notificationsUserId, setNotificationsUserId] = useState("11111111-1111-1111-1111-111111111111");
  const [notifications, setNotifications] = useState<Array<{ id: string; type: string; message: string; created_at: string }>>([]);

  const txnId = init?.txnId ?? status?.id ?? null;

  const step = useMemo(() => {
    if (!init && !status) return "FORM";
    if (status?.status && status.status !== "HOLD") return "RESULT";
    if (status?.status === "HOLD") return "HOLD";
    if (init?.status === "HOLD") return "HOLD";
    return "RESULT";
  }, [init, status]);

  async function refreshStatus(id: string) {
    const s = await getPaymentStatus(id);
    setStatus(s);
    return s;
  }

  useEffect(() => {
    if (!txnId) return;
    const t = window.setInterval(() => {
      refreshStatus(txnId).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(t);
  }, [txnId]);

  useEffect(() => {
    if (step !== "HOLD") return;
    const expires = init?.holdExpiresAt ?? status?.hold_expires_at ?? null;
    if (!expires) return;
    const update = () => {
      const remaining = Math.max(0, new Date(expires).getTime() - Date.now());
      setHoldRemainingMs(remaining);
      if (remaining <= 0 && txnId) refreshStatus(txnId).catch(() => undefined);
    };
    update();
    const t = window.setInterval(update, 500);
    return () => window.clearInterval(t);
  }, [step, init?.holdExpiresAt, status?.hold_expires_at, txnId]);

  const holdTimerLabel = useMemo(() => {
    const total = Math.ceil(holdRemainingMs / 1000);
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }, [holdRemainingMs]);

  async function onInitiate() {
    setBusy(true);
    setErr(null);
    setStatus(null);
    try {
      const r = await initiatePayment({
        idempotencyKey: idempotencyKey.trim() ? idempotencyKey.trim() : undefined,
        senderVpa: senderVpa.trim(),
        receiverVpa: receiverVpa.trim(),
        amount: Number(amount),
        deviceId: deviceId.trim(),
        location: location.trim(),
      });
      setInit(r);
      if (r.status !== "HOLD") {
        await refreshStatus(r.txnId);
      } else {
        setOtp(r.otpDebug ?? "");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
      setErr(msg === "BACKEND_INVALID_JSON" ? "Backend returned invalid JSON. Restart backend + refresh the page." : msg);
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!init?.txnId) return;
    if (status?.status && status.status !== "HOLD") {
      setErr("Transaction is not in HOLD anymore. Refreshing status...");
      await refreshStatus(init.txnId).catch(() => undefined);
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const s = await confirmPayment({ txnId: init.txnId, otp, pin });
      setStatus(s);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
      if (msg === "NOT_HOLD") {
        setErr("Transaction is not in HOLD anymore. Refreshing status...");
        await refreshStatus(init.txnId).catch(() => undefined);
      } else {
        setErr(msg === "BACKEND_INVALID_JSON" ? "Backend returned invalid JSON. Restart backend + refresh the page." : msg);
      }
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    if (!init?.txnId) return;
    if (status?.status && status.status !== "HOLD") {
      setErr("Transaction is not in HOLD anymore. Refreshing status...");
      await refreshStatus(init.txnId).catch(() => undefined);
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const s = await cancelPayment({ txnId: init.txnId, actorUserId: notificationsUserId.trim() || undefined });
      setStatus(s);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
      if (msg === "NOT_HOLD") {
        setErr("Transaction is not in HOLD anymore. Refreshing status...");
        await refreshStatus(init.txnId).catch(() => undefined);
      } else {
        setErr(msg === "BACKEND_INVALID_JSON" ? "Backend returned invalid JSON. Restart backend + refresh the page." : msg);
      }
    } finally {
      setBusy(false);
    }
  }

  async function onLoadNotifications() {
    setBusy(true);
    setErr(null);
    try {
      const r = await getNotifications(notificationsUserId.trim());
      setNotifications(r.items);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
      setErr(msg === "BACKEND_INVALID_JSON" ? "Backend returned invalid JSON. Restart backend + refresh the page." : msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 px-4 py-10 text-zinc-900">
      <div className="mx-auto w-full max-w-4xl">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">ApexPay</h1>
            <p className="text-sm text-zinc-600">Risk-aware UPI simulation with HOLD + ML fraud scoring</p>
          </div>
          <div className="text-right text-xs text-zinc-500">
            <div>Backend: {process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:4000"}</div>
          </div>
        </div>

        {err ? (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{err}</div>
        ) : null}

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-zinc-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Payment</h2>
              <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs text-zinc-700">{step}</span>
            </div>

            <div className="mt-4 grid gap-3">
              <label className="grid gap-1 text-sm">
                <span className="text-zinc-700">Sender VPA</span>
                <input className="h-10 rounded-xl border border-zinc-200 px-3" value={senderVpa} onChange={(e) => setSenderVpa(e.target.value)} />
              </label>
              <label className="grid gap-1 text-sm">
                <span className="text-zinc-700">Receiver VPA</span>
                <input className="h-10 rounded-xl border border-zinc-200 px-3" value={receiverVpa} onChange={(e) => setReceiverVpa(e.target.value)} />
              </label>
              <label className="grid gap-1 text-sm">
                <span className="text-zinc-700">Amount (INR)</span>
                <input className="h-10 rounded-xl border border-zinc-200 px-3" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="grid gap-1 text-sm">
                  <span className="text-zinc-700">Device ID</span>
                  <input className="h-10 rounded-xl border border-zinc-200 px-3" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} />
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-zinc-700">Location</span>
                  <input className="h-10 rounded-xl border border-zinc-200 px-3" value={location} onChange={(e) => setLocation(e.target.value)} />
                </label>
              </div>
              <label className="grid gap-1 text-sm">
                <span className="text-zinc-700">Idempotency Key (optional)</span>
                <input className="h-10 rounded-xl border border-zinc-200 px-3" value={idempotencyKey} onChange={(e) => setIdempotencyKey(e.target.value)} />
              </label>

              <button
                className="mt-2 h-11 rounded-xl bg-zinc-900 text-sm font-semibold text-white disabled:opacity-60"
                onClick={onInitiate}
                disabled={busy}
              >
                Initiate Payment
              </button>
            </div>

            {init ? (
              <div className="mt-5 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm">
                <div className="flex items-center justify-between">
                  <div className="font-medium">Risk Decision</div>
                  <div className="rounded-full bg-white px-2 py-1 text-xs">{init.decision}</div>
                </div>
                <div className="mt-1 text-xs text-zinc-600">Txn: {init.txnId}</div>
                <div className="mt-2 grid gap-1 text-xs text-zinc-700">
                  <div>Risk score: {init.riskScore.toFixed(3)}</div>
                  <div>Fraud type: {init.fraudType}</div>
                  <div>Reasons: {init.reasons.length ? init.reasons.join(" • ") : "—"}</div>
                  {init.otpRequired ? <div>OTP required</div> : null}
                </div>
              </div>
            ) : null}

            {step === "HOLD" ? (
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-amber-900">HOLD: Confirmation needed</div>
                  <div className="text-sm font-semibold text-amber-900">{holdTimerLabel}</div>
                </div>
                <div className="mt-3 grid gap-2">
                  <label className="grid gap-1 text-sm">
                    <span className="text-amber-900">OTP (6 digits)</span>
                    <input className="h-10 rounded-lg border border-amber-200 bg-white px-3" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="123456" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    <span className="text-amber-900">PIN (demo: 1234)</span>
                    <input className="h-10 rounded-lg border border-amber-200 bg-white px-3" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="****" />
                  </label>
                  {init?.otpDebug ? <div className="text-xs text-amber-900">Dev OTP: {init.otpDebug}</div> : null}
                  <div className="mt-1 grid grid-cols-2 gap-2">
                    <button
                      className="h-10 rounded-xl bg-amber-900 text-sm font-semibold text-white disabled:opacity-60"
                      onClick={onConfirm}
                      disabled={busy || otp.trim().length !== 6 || pin.trim().length < 4}
                    >
                      Confirm
                    </button>
                    <button className="h-10 rounded-xl border border-amber-300 bg-white text-sm font-semibold text-amber-900 disabled:opacity-60" onClick={onCancel} disabled={busy}>
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="grid gap-6">
            <div className="rounded-2xl border border-zinc-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Transaction Status</h2>
                <button className="h-9 rounded-xl border border-zinc-200 bg-white px-3 text-sm disabled:opacity-60" disabled={!txnId || busy} onClick={() => txnId && refreshStatus(txnId)}>
                  Refresh
                </button>
              </div>
              <div className="mt-4 text-sm">
                {!txnId ? (
                  <div className="text-zinc-600">No transaction yet.</div>
                ) : (
                  <div className="grid gap-1">
                    <div>
                      <span className="text-zinc-500">Txn:</span> {txnId}
                    </div>
                    <div>
                      <span className="text-zinc-500">Status:</span> {status?.status ?? init?.status}
                    </div>
                    <div>
                      <span className="text-zinc-500">Amount:</span> ₹{status?.amount ?? Number(amount)}
                    </div>
                    <div>
                      <span className="text-zinc-500">Decision:</span> {status?.decision ?? init?.decision}
                    </div>
                    <div>
                      <span className="text-zinc-500">Reason:</span> {status?.decision_reason ?? (init ? init.reasons.join(" | ") : "—")}
                    </div>
                    {status?.failure_reason ? (
                      <div>
                        <span className="text-zinc-500">Failure:</span> {status.failure_reason}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-200 bg-white p-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">Notifications</h2>
                <button className="h-9 rounded-xl border border-zinc-200 bg-white px-3 text-sm disabled:opacity-60" disabled={busy} onClick={onLoadNotifications}>
                  Load
                </button>
              </div>
              <div className="mt-3 grid gap-2">
                <label className="grid gap-1 text-sm">
                  <span className="text-zinc-700">User ID</span>
                  <input className="h-10 rounded-xl border border-zinc-200 px-3" value={notificationsUserId} onChange={(e) => setNotificationsUserId(e.target.value)} />
                </label>
                <div className="max-h-64 overflow-auto rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-sm">
                  {notifications.length === 0 ? (
                    <div className="text-zinc-600">No notifications loaded.</div>
                  ) : (
                    <div className="grid gap-2">
                      {notifications.map((n) => (
                        <div key={n.id} className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
                          <div className="flex items-center justify-between text-xs text-zinc-500">
                            <span>{n.type}</span>
                            <span>{n.created_at}</span>
                          </div>
                          <div className="mt-1">{n.message}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
