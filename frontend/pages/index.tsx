import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import CheckBalance from "../components/CheckBalance";
import {
  cancelPayment,
  confirmPayment,
  getNotifications,
  getPaymentStatus,
  initiatePayment,
  loginInitiate,
  loginVerifyOtp,
  loginVerifyPin,
  registerInitiate,
  registerSetPin,
  registerVerifyOtp,
  resolveReceiver,
  simulateSettlementFailure,
  type AuthUser,
  type InitiateResponse,
  type TxStatusResponse,
} from "../services/backend";

export default function Home() {
  // Auth State
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authMode, setAuthMode] = useState<"LOGIN" | "REGISTER">("LOGIN");
  const [authStep, setAuthStep] = useState<"INIT" | "OTP" | "PIN">("INIT");
  const [authLoading, setAuthLoading] = useState(true);

  // Form State
  const [receiverMode, setReceiverMode] = useState<"VPA" | "MOBILE">("VPA");
  const [senderVpa, setSenderVpa] = useState("");
  const [receiverVpa, setReceiverVpa] = useState("isha@neo");
  const [receiverMobile, setReceiverMobile] = useState("");
  const [amount, setAmount] = useState("1000");
  const [deviceId, setDeviceId] = useState("device_web_1");
  const [location, setLocation] = useState("IN-MH");

  // Auth Form Fields
  const [authMobile, setAuthMobile] = useState("");
  const [authFirstName, setAuthFirstName] = useState("");
  const [authLastName, setAuthLastName] = useState("");
  const [authOtp, setAuthOtp] = useState("");
  const [authPin, setAuthPin] = useState("");
  const [availableBanks, setAvailableBanks] = useState<Array<{ id: string; bankName: string; accountNumber: string }>>([]);
  const [selectedBankId, setSelectedBankId] = useState("");

  const [init, setInit] = useState<InitiateResponse | null>(null);
  const [status, setStatus] = useState<TxStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [otp, setOtp] = useState("");
  const [pin, setPin] = useState("");
  const [holdRemainingMs, setHoldRemainingMs] = useState(0);

  const [notificationsUserId, setNotificationsUserId] = useState("");
  const [notifications, setNotifications] = useState<Array<{ id: string; type: string; message: string; created_at: string }>>([]);
  const [chaosMode, setChaosMode] = useState<"NONE" | "AFTER_DEBIT" | "BEFORE_CREDIT">("NONE");
  const [activeTab, setActiveTab] = useState<"VPA" | "MOBILE" | "BALANCE">("VPA");
  const [paymentFlowStep, setPaymentFlowStep] = useState<"INPUT" | "CONFIRM_RECEIVER" | "ENTER_PIN" | "FINAL_CONFIRM">("INPUT");
  const [resolvedReceiver, setResolvedReceiver] = useState<{ name: string; vpa: string } | null>(null);

  const txnId = init?.txnId ?? status?.id ?? null;

  const step = useMemo(() => {
    if (!init && !status) return "FORM";
    if (status?.status && status.status !== "HOLD") return "RESULT";
    if (status?.status === "HOLD") return "HOLD";
    if (init?.status === "HOLD") return "HOLD";
    return "RESULT";
  }, [init, status]);

  useEffect(() => {
    const savedToken = localStorage.getItem("apexpay_token");
    const savedUser = localStorage.getItem("apexpay_user");
    if (savedToken && savedUser) {
      try {
        const u = JSON.parse(savedUser);
        setUser(u);
        setSenderVpa(u.vpa || "");
        setNotificationsUserId(u.id);
      } catch (e) {
        localStorage.removeItem("apexpay_token");
        localStorage.removeItem("apexpay_user");
      }
    }
    setAuthLoading(false);
  }, []);

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

  function onPayClick() {
    setPaymentFlowStep("ENTER_PIN");
  }

  async function onPinSubmit() {
    setBusy(true);
    setErr(null);
    try {
      const r = await resolveReceiver(
        receiverMode === "VPA" ? receiverVpa.trim() : undefined,
        receiverMode === "MOBILE" ? receiverMobile.trim() : undefined
      );
      setResolvedReceiver(r);
      setPaymentFlowStep("CONFIRM_RECEIVER");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "RECEIVER_NOT_FOUND");
      setPaymentFlowStep("INPUT");
    } finally {
      setBusy(false);
    }
  }

  async function onInitiate() {
    setBusy(true);
    setErr(null);
    setStatus(null);
    try {
      if (chaosMode !== "NONE") {
        // We don't have txnId yet, but simulateSettlementFailure sets a global point for next txn
        await simulateSettlementFailure("00000000-0000-0000-0000-000000000000", chaosMode as any);
      }
      const r = await initiatePayment({
        senderVpa: senderVpa.trim() || user?.vpa || "",
        receiverVpa: receiverMode === "VPA" ? receiverVpa.trim() : undefined,
        receiverMobile: receiverMode === "MOBILE" ? receiverMobile.trim() : undefined,
        amount: Number(amount),
        deviceId: deviceId.trim(),
        location: location.trim(),
        pin: pin.trim(),
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
    console.log("Confirming transaction:", init.txnId, "with OTP:", otp);
    try {
      const s = await confirmPayment({ txnId: init.txnId, otp, pin });
      console.log("Confirmation result:", s);
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

  function onReset() {
    setInit(null);
    setStatus(null);
    setErr(null);
    setOtp("");
    setPin("");
    setPaymentFlowStep("INPUT");
    setResolvedReceiver(null);
  }

  async function onAuthInitiate() {
    setBusy(true);
    setErr(null);
    try {
      if (authMode === "LOGIN") {
        const r = await loginInitiate(authMobile);
        if (r.otpDebug) setAuthOtp(r.otpDebug);
        setAuthStep("OTP");
      } else {
        const r = await registerInitiate({
          mobileNumber: authMobile,
          firstName: authFirstName,
          lastName: authLastName,
        });
        if (r.otpDebug) setAuthOtp(r.otpDebug);
        setAvailableBanks(r.availableBanks);
        if (r.availableBanks.length > 0) setSelectedBankId(r.availableBanks[0].id);
        setAuthStep("OTP");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "AUTH_INIT_FAILED");
    } finally {
      setBusy(false);
    }
  }

  async function onAuthVerifyOtp() {
    setBusy(true);
    setErr(null);
    try {
      if (authMode === "LOGIN") {
        await loginVerifyOtp(authMobile, authOtp);
        setAuthStep("PIN");
      } else {
        await registerVerifyOtp(authMobile, authOtp);
        setAuthStep("PIN");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "OTP_VERIFY_FAILED");
    } finally {
      setBusy(false);
    }
  }

  async function onAuthComplete() {
    setBusy(true);
    setErr(null);
    try {
      if (authMode === "LOGIN") {
        const r = await loginVerifyPin(authMobile, authPin);
        localStorage.setItem("apexpay_token", r.token);
        localStorage.setItem("apexpay_user", JSON.stringify(r.user));
        setUser(r.user);
        setSenderVpa(r.user.vpa || "");
        setNotificationsUserId(r.user.id);
      } else {
        const r = await registerSetPin({
          mobileNumber: authMobile,
          firstName: authFirstName,
          lastName: authLastName,
          pin: authPin,
          bankAccountId: selectedBankId,
        });
        // After registration, auto-login
        setAuthMode("LOGIN");
        setAuthStep("PIN");
        setAuthPin("");
        alert(`Registration successful! Your VPA is ${r.vpa}. Please login with your PIN.`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "AUTH_COMPLETE_FAILED");
    } finally {
      setBusy(false);
    }
  }

  function onLogout() {
    localStorage.removeItem("apexpay_token");
    localStorage.removeItem("apexpay_user");
    setUser(null);
    setAuthStep("INIT");
    setAuthMobile("");
    setAuthPin("");
    setAuthOtp("");
  }

  if (authLoading) return <div className="flex min-h-screen items-center justify-center">Loading...</div>;

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-100 px-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-bold text-zinc-900">ApexPay</h1>
            <p className="text-zinc-500">{authMode === "LOGIN" ? "Welcome back" : "Join the banking revolution"}</p>
          </div>

          {err && (
            <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {err === "NUMBER_NOT_LINKED_TO_BANK" ? (
                <span>
                  Your mobile is not linked to any bank. 
                  <Link href="/bankPage" className="ml-1 underline font-bold">Link it here</Link>
                </span>
              ) : err}
            </div>
          )}

          {authStep === "INIT" && (
            <div className="space-y-4">
              {authMode === "REGISTER" && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider">First Name</label>
                    <input
                      type="text"
                      className="mt-1 w-full rounded-lg border border-zinc-200 p-3 outline-none focus:ring-2 focus:ring-blue-500"
                      value={authFirstName}
                      onChange={(e) => setAuthFirstName(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider">Last Name</label>
                    <input
                      type="text"
                      className="mt-1 w-full rounded-lg border border-zinc-200 p-3 outline-none focus:ring-2 focus:ring-blue-500"
                      value={authLastName}
                      onChange={(e) => setAuthLastName(e.target.value)}
                    />
                  </div>
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider">Mobile Number</label>
                <input
                  type="text"
                  placeholder="9000000001"
                  className="mt-1 w-full rounded-lg border border-zinc-200 p-3 outline-none focus:ring-2 focus:ring-blue-500"
                  value={authMobile}
                  onChange={(e) => setAuthMobile(e.target.value)}
                />
              </div>
              <button
                disabled={busy}
                onClick={onAuthInitiate}
                className="w-full rounded-lg bg-blue-600 p-3 font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Processing..." : "Continue"}
              </button>
            </div>
          )}

          {authStep === "OTP" && (
            <div className="space-y-4">
              <p className="text-sm text-zinc-600">Enter the 6-digit OTP sent to {authMobile}</p>
              <input
                type="text"
                placeholder="000000"
                className="w-full rounded-lg border border-zinc-200 p-3 text-center text-2xl font-bold tracking-[1em] outline-none focus:ring-2 focus:ring-blue-500"
                value={authOtp}
                onChange={(e) => setAuthOtp(e.target.value)}
                maxLength={6}
              />
              {authMode === "REGISTER" && availableBanks.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider">Select Bank Account</label>
                  <select
                    className="mt-1 w-full rounded-lg border border-zinc-200 p-3 outline-none focus:ring-2 focus:ring-blue-500"
                    value={selectedBankId}
                    onChange={(e) => setSelectedBankId(e.target.value)}
                  >
                    {availableBanks.map(bank => (
                      <option key={bank.id} value={bank.id}>
                        {bank.bankName} - {bank.accountNumber}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <button
                disabled={busy}
                onClick={onAuthVerifyOtp}
                className="w-full rounded-lg bg-blue-600 p-3 font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Verifying..." : "Verify OTP"}
              </button>
            </div>
          )}

          {authStep === "PIN" && (
            <div className="space-y-4">
              <label className="block text-xs font-medium text-zinc-500 uppercase tracking-wider">
                {authMode === "LOGIN" ? "Enter your Secure PIN" : "Set a new 4-6 digit PIN"}
              </label>
              <input
                type="password"
                placeholder="****"
                className="w-full rounded-lg border border-zinc-200 p-3 text-center text-2xl font-bold tracking-[1em] outline-none focus:ring-2 focus:ring-blue-500"
                value={authPin}
                onChange={(e) => setAuthPin(e.target.value)}
                maxLength={6}
              />
              <button
                disabled={busy}
                onClick={onAuthComplete}
                className="w-full rounded-lg bg-blue-600 p-3 font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Authenticating..." : (authMode === "LOGIN" ? "Login" : "Complete Registration")}
              </button>
            </div>
          )}

          <div className="mt-8 text-center text-sm space-y-2">
            <button
              className="text-blue-600 hover:underline block w-full"
              onClick={() => {
                setAuthMode(authMode === "LOGIN" ? "REGISTER" : "LOGIN");
                setAuthStep("INIT");
                setErr(null);
              }}
            >
              {authMode === "LOGIN" ? "Don't have an account? Register" : "Already have an account? Login"}
            </button>
            <div className="pt-4 border-t border-zinc-100">
              <Link href="/bankPage" className="text-zinc-400 hover:text-zinc-600 transition-colors">
                Bank Employee Portal (Simulation)
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #e4e4e7;
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #d4d4d8;
        }
      `}</style>
      <div className="flex h-screen overflow-hidden">
        {/* Side Navigator */}
        <div className="w-72 flex-shrink-0 border-r border-zinc-200 bg-white flex flex-col">
          <div className="p-8">
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-white text-xl font-black shadow-lg shadow-blue-200">
                A
              </div>
              <div>
                <h1 className="text-xl font-black tracking-tight text-zinc-900">ApexPay</h1>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></span>
                  <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">System Active</p>
                </div>
              </div>
            </div>
          </div>
          
          <nav className="flex-1 px-4 space-y-1.5">
            <div className="px-4 py-2">
              <p className="text-[10px] font-black text-zinc-400 uppercase tracking-[0.2em]">Payments</p>
            </div>
            <button
              onClick={() => { setActiveTab("VPA"); setReceiverMode("VPA"); }}
              className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl text-sm font-bold transition-all duration-200 group ${
                activeTab === "VPA" 
                  ? "bg-blue-600 text-white shadow-xl shadow-blue-100 translate-x-1" 
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              <span className={`text-lg transition-transform duration-200 ${activeTab === "VPA" ? "scale-110" : "group-hover:scale-110"}`}>💳</span>
              Pay via VPA
            </button>
            
            <button
              onClick={() => { setActiveTab("MOBILE"); setReceiverMode("MOBILE"); }}
              className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl text-sm font-bold transition-all duration-200 group ${
                activeTab === "MOBILE" 
                  ? "bg-blue-600 text-white shadow-xl shadow-blue-100 translate-x-1" 
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              <span className={`text-lg transition-transform duration-200 ${activeTab === "MOBILE" ? "scale-110" : "group-hover:scale-110"}`}>📱</span>
              Pay via Mobile
            </button>

            <div className="px-4 py-2 mt-4">
              <p className="text-[10px] font-black text-zinc-400 uppercase tracking-[0.2em]">Account</p>
            </div>
            
            <button
              onClick={() => setActiveTab("BALANCE")}
              className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl text-sm font-bold transition-all duration-200 group ${
                activeTab === "BALANCE" 
                  ? "bg-blue-600 text-white shadow-xl shadow-blue-100 translate-x-1" 
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              <span className={`text-lg transition-transform duration-200 ${activeTab === "BALANCE" ? "scale-110" : "group-hover:scale-110"}`}>💰</span>
              Check Balance
            </button>
          </nav>

          <div className="p-6 mt-auto">
            <div className="rounded-3xl bg-zinc-50 p-5 border border-zinc-100">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-md">
                  {user.firstName[0]}{user.lastName[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-black text-zinc-900 truncate">{user.firstName} {user.lastName}</p>
                  <p className="text-[10px] font-bold text-zinc-400 truncate">{user.mobile}</p>
                </div>
              </div>
              <button
                onClick={onLogout}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-white border border-zinc-200 px-4 py-2.5 text-xs font-black text-red-600 hover:bg-red-50 hover:border-red-100 hover:text-red-700 transition-all active:scale-95 shadow-sm"
              >
                <span>🚪</span> Logout
              </button>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto bg-zinc-50 p-10">
          <div className="mx-auto max-w-5xl">
            <header className="mb-10 flex items-end justify-between">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-0.5 rounded bg-blue-100 text-[10px] font-black text-blue-700 uppercase tracking-widest">Dashboard</span>
                </div>
                <h2 className="text-3xl font-black text-zinc-900 tracking-tight">
                  {activeTab === "VPA" ? "Pay via VPA" : 
                   activeTab === "MOBILE" ? "Pay via Mobile" : 
                   "Account Balance"}
                </h2>
                <p className="text-zinc-500 text-sm font-medium mt-1">Manage your funds and transactions securely.</p>
              </div>
              <div className="text-right bg-white px-6 py-3 rounded-2xl border border-zinc-200 shadow-sm">
                <p className="text-[10px] font-black text-zinc-400 uppercase tracking-widest mb-1">Your Primary VPA</p>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                  <p className="font-mono text-sm font-black text-zinc-900">{senderVpa}</p>
                </div>
              </div>
            </header>

            {err ? (
              <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex items-center gap-2">
                <span>⚠️</span> {err}
              </div>
            ) : null}

            <div className="grid gap-8 lg:grid-cols-12">
              <div className="lg:col-span-7 space-y-6">
                {activeTab === "BALANCE" ? (
                  <CheckBalance />
                ) : (
                  <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
                    <div className="flex items-center justify-between mb-8">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl shadow-lg ${
                          activeTab === "VPA" ? "bg-blue-100 text-blue-600 shadow-blue-50" : "bg-purple-100 text-purple-600 shadow-purple-50"
                        }`}>
                          {activeTab === "VPA" ? "💳" : "📱"}
                        </div>
                        <div>
                          <h3 className="text-lg font-black text-zinc-900">Transaction Details</h3>
                          <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Step 1: Initiation</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button 
                          onClick={onReset} 
                          className="h-8 px-3 rounded-lg bg-zinc-50 text-[10px] font-black text-zinc-500 uppercase tracking-widest hover:bg-zinc-100 transition-colors"
                        >
                          Reset
                        </button>
                        <span className="h-8 px-3 rounded-lg bg-blue-50 text-[10px] font-black text-blue-600 uppercase tracking-widest flex items-center">
                          {step}
                        </span>
                      </div>
                    </div>

                    {step === "FORM" ? (
                      <div className="grid gap-6">
                        {paymentFlowStep === "INPUT" ? (
                          <>
                            <div className="grid gap-2">
                              <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest ml-1">From Account (Auto-detected)</span>
                              <div className="h-14 rounded-2xl border border-zinc-100 bg-zinc-50 px-5 flex items-center justify-between group transition-all">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
                                    {user.firstName[0]}
                                  </div>
                                  <span className="font-mono text-sm font-black text-zinc-400 group-hover:text-zinc-600 transition-colors">{senderVpa}</span>
                                </div>
                                <span className="text-[10px] font-black text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded uppercase tracking-widest">Verified</span>
                              </div>
                            </div>

                            {activeTab === "VPA" ? (
                              <div className="grid gap-2">
                                <span className="text-[10px] font-black text-zinc-700 uppercase tracking-widest ml-1">Recipient VPA Address</span>
                                <div className="relative">
                                  <input
                                    placeholder="username@apex"
                                    className="h-14 w-full rounded-2xl border border-zinc-200 px-5 text-sm font-bold outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all placeholder:text-zinc-300"
                                    value={receiverVpa}
                                    onChange={(e) => setReceiverVpa(e.target.value)}
                                  />
                                  <div className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-300 pointer-events-none">
                                    <span className="text-lg">✨</span>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="grid gap-2">
                                <span className="text-[10px] font-black text-zinc-700 uppercase tracking-widest ml-1">Recipient Mobile Number</span>
                                <div className="relative">
                                  <input
                                    placeholder="9000000001"
                                    className="h-14 w-full rounded-2xl border border-zinc-200 px-5 text-sm font-bold outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all placeholder:text-zinc-300"
                                    value={receiverMobile}
                                    onChange={(e) => setReceiverMobile(e.target.value)}
                                  />
                                  <div className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-300 pointer-events-none">
                                    <span className="text-lg">📞</span>
                                  </div>
                                </div>
                              </div>
                            )}

                            <div className="grid gap-2">
                              <span className="text-[10px] font-black text-zinc-700 uppercase tracking-widest ml-1">Transfer Amount</span>
                              <div className="relative">
                                <span className="absolute left-5 top-1/2 -translate-y-1/2 text-zinc-400 font-black text-xl">₹</span>
                                <input 
                                  className="h-14 w-full rounded-2xl border border-zinc-200 pl-10 pr-5 text-2xl font-black outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all text-zinc-900" 
                                  value={amount} 
                                  onChange={(e) => setAmount(e.target.value)} 
                                />
                                <div className="absolute right-5 top-1/2 -translate-y-1/2 flex gap-2">
                                  <button onClick={() => setAmount("500")} className="px-2 py-1 rounded bg-zinc-50 text-[10px] font-black text-zinc-500 hover:bg-zinc-100 transition-colors">500</button>
                                  <button onClick={() => setAmount("1000")} className="px-2 py-1 rounded bg-zinc-50 text-[10px] font-black text-zinc-500 hover:bg-zinc-100 transition-colors">1K</button>
                                  <button onClick={() => setAmount("5000")} className="px-2 py-1 rounded bg-zinc-50 text-[10px] font-black text-zinc-500 hover:bg-zinc-100 transition-colors">5K</button>
                                </div>
                              </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                              <div className="grid gap-2">
                                <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest ml-1">Device Binding</span>
                                <input className="h-12 rounded-xl border border-zinc-100 px-4 text-xs font-bold text-zinc-400 bg-zinc-50/50" value={deviceId} readOnly />
                              </div>
                              <div className="grid gap-2">
                                <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest ml-1">Geographic Context</span>
                                <input className="h-12 rounded-xl border border-zinc-100 px-4 text-xs font-bold text-zinc-400 bg-zinc-50/50" value={location} readOnly />
                              </div>
                            </div>

                            <div className="grid gap-2">
                              <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest ml-1">Simulation Parameters</span>
                              <select 
                                className="h-12 rounded-xl border border-zinc-200 px-4 bg-white text-xs font-bold text-zinc-700 outline-none focus:ring-2 focus:ring-blue-500 transition-all appearance-none cursor-pointer" 
                                value={chaosMode} 
                                onChange={(e) => setChaosMode(e.target.value as any)}
                              >
                                <option value="NONE">Success Path (Recommended)</option>
                                <option value="AFTER_DEBIT">Simulate: Crash After Debit</option>
                                <option value="BEFORE_CREDIT">Simulate: Crash Before Credit</option>
                              </select>
                            </div>

                            <button
                              className="mt-4 h-16 rounded-2xl bg-blue-600 text-sm font-black text-white shadow-xl shadow-blue-100 hover:bg-blue-700 transition-all active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-3"
                              onClick={onPayClick}
                              disabled={busy}
                            >
                              <span className="text-lg">🛡️</span>
                              Pay Now
                            </button>
                          </>
                        ) : paymentFlowStep === "CONFIRM_RECEIVER" ? (
                          <div className="p-6 rounded-3xl bg-blue-50 border border-blue-100">
                            <h4 className="text-[10px] font-black text-blue-400 uppercase tracking-widest mb-6">Confirm Recipient Details</h4>
                            <div className="space-y-4">
                              <div className="flex justify-between items-center py-3 border-b border-blue-100/50">
                                <span className="text-xs font-bold text-blue-600">Receiver Name</span>
                                <span className="text-sm font-black text-blue-900">{resolvedReceiver?.name}</span>
                              </div>
                              <div className="flex justify-between items-center py-3 border-b border-blue-100/50">
                                <span className="text-xs font-bold text-blue-600">VPA Address</span>
                                <span className="text-sm font-mono font-black text-blue-900">{resolvedReceiver?.vpa}</span>
                              </div>
                              <div className="flex justify-between items-center py-3">
                                <span className="text-xs font-bold text-blue-600">Amount to Transfer</span>
                                <span className="text-xl font-black text-blue-900">₹{amount}</span>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mt-8">
                              <button 
                                onClick={() => setPaymentFlowStep("ENTER_PIN")}
                                className="h-12 rounded-xl bg-white border border-blue-200 text-xs font-black text-blue-600 hover:bg-blue-100 transition-all"
                              >
                                Back
                              </button>
                              <button 
                                onClick={onInitiate}
                                className="h-12 rounded-xl bg-blue-600 text-xs font-black text-white shadow-lg shadow-blue-200 hover:bg-blue-700 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                disabled={busy}
                              >
                                {busy ? (
                                  <>
                                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                    Processing...
                                  </>
                                ) : "Confirm & Pay"}
                              </button>
                            </div>
                          </div>
                        ) : paymentFlowStep === "ENTER_PIN" ? (
                          <div className="p-6 rounded-3xl bg-zinc-50 border border-zinc-200">
                            <h4 className="text-[10px] font-black text-zinc-400 uppercase tracking-widest mb-6 text-center">Security Verification</h4>
                            <div className="flex flex-col items-center gap-6">
                              <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center text-2xl mb-2">
                                🔐
                              </div>
                              <div className="w-full max-w-[240px]">
                                <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest block text-center mb-2">Enter your 4-6 digit PIN</span>
                                <input
                                  type="password"
                                  className="w-full h-14 rounded-2xl border-2 border-zinc-200 bg-white text-center text-2xl font-black tracking-[0.5em] outline-none focus:border-blue-500 transition-all"
                                  value={pin}
                                  onChange={(e) => setPin(e.target.value)}
                                  placeholder="••••"
                                  maxLength={6}
                                  autoFocus
                                />
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mt-8">
                              <button 
                                onClick={() => setPaymentFlowStep("INPUT")}
                                className="h-12 rounded-xl bg-white border border-zinc-200 text-xs font-black text-zinc-600 hover:bg-zinc-100 transition-all"
                              >
                                Back
                              </button>
                              <button 
                                onClick={onPinSubmit}
                                className="h-12 rounded-xl bg-blue-600 text-xs font-black text-white shadow-lg shadow-blue-200 hover:bg-blue-700 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                disabled={pin.length < 4 || busy}
                              >
                                {busy ? (
                                  <>
                                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                    Verifying...
                                  </>
                                ) : "Submit PIN"}
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {init && step !== "FORM" ? (
                      <div className="mt-8 rounded-3xl border border-zinc-100 bg-zinc-50 p-6 shadow-inner">
                        <div className="flex items-center justify-between mb-6">
                          <div>
                            <h4 className="text-[10px] font-black text-zinc-400 uppercase tracking-[0.2em] mb-1">Risk Intelligence Analysis</h4>
                            <p className="text-xs font-bold text-zinc-600">Automated fraud detection engine result</p>
                          </div>
                          <div className={`rounded-xl px-4 py-2 text-[10px] font-black uppercase tracking-widest shadow-sm ${
                            init.decision === "HIGH" ? "bg-red-500 text-white shadow-red-100" :
                            init.decision === "MEDIUM" ? "bg-amber-500 text-white shadow-amber-100" :
                            "bg-emerald-500 text-white shadow-emerald-100"
                          }`}>
                            {init.decision} Risk Score
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-6">
                          <div className="p-4 rounded-2xl bg-white border border-zinc-100">
                            <span className="text-[9px] font-black text-zinc-400 uppercase tracking-widest block mb-1">Transaction Token</span>
                            <span className="font-mono text-[11px] font-black text-zinc-900">{init.txnId.split('-')[0]}...</span>
                          </div>
                          <div className="p-4 rounded-2xl bg-white border border-zinc-100">
                            <span className="text-[9px] font-black text-zinc-400 uppercase tracking-widest block mb-1">Calculated Probability</span>
                            <span className="font-black text-zinc-900 text-sm">{(init.riskScore * 100).toFixed(2)}%</span>
                          </div>
                        </div>
                        <div className="mt-4 p-4 rounded-2xl bg-blue-600/5 border border-blue-600/10">
                          <span className="text-[9px] font-black text-blue-600 uppercase tracking-widest block mb-1">Neural Flags</span>
                          <span className="text-xs font-bold text-blue-700">{init.fraudType || "NONE_DETECTED"}</span>
                        </div>
                      </div>
                    ) : null}

                    {step === "HOLD" ? (
                      <div className="mt-8 rounded-3xl border-2 border-amber-200 bg-amber-50/50 p-8 relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-4">
                          <div className="flex items-center gap-2 bg-amber-200/50 px-3 py-1.5 rounded-full">
                            <span className="w-2 h-2 bg-amber-500 rounded-full animate-ping"></span>
                            <span className="font-mono text-xs font-black text-amber-900">{holdTimerLabel}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-4 mb-8">
                          <div className="w-12 h-12 bg-amber-200 rounded-2xl flex items-center justify-center text-2xl shadow-lg shadow-amber-100">
                            🛡️
                          </div>
                          <div>
                            <h4 className="text-lg font-black text-amber-900">Security Challenge</h4>
                            <p className="text-xs font-bold text-amber-700/70">Verify your identity to complete transfer</p>
                          </div>
                        </div>
                        
                        <div className="space-y-6">
                          <div className="grid grid-cols-2 gap-6">
                            <div className="space-y-2">
                              <span className="text-[10px] font-black text-amber-800 uppercase tracking-widest ml-1">OTP (6-Digit)</span>
                              <input 
                                className="h-16 w-full rounded-2xl border border-amber-200 bg-white px-4 text-center text-2xl font-black tracking-[0.5em] focus:ring-4 focus:ring-amber-500/10 focus:border-amber-500 outline-none transition-all" 
                                value={otp} 
                                onChange={(e) => setOtp(e.target.value)} 
                                placeholder="000000" 
                                maxLength={6}
                              />
                            </div>
                            <div className="space-y-2">
                              <span className="text-[10px] font-black text-amber-800 uppercase tracking-widest ml-1">Secure PIN</span>
                              <input 
                                type="password"
                                className="h-16 w-full rounded-2xl border border-amber-200 bg-white px-4 text-center text-2xl font-black tracking-[0.5em] focus:ring-4 focus:ring-amber-500/10 focus:border-amber-500 outline-none transition-all" 
                                value={pin} 
                                onChange={(e) => setPin(e.target.value)} 
                                placeholder="••••" 
                                maxLength={6}
                              />
                            </div>
                          </div>

                          {init?.otpDebug ? (
                            <div className="flex items-center justify-between rounded-2xl bg-amber-200/40 px-5 py-3 border border-amber-200/50">
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] font-black text-amber-900 uppercase tracking-widest">Dev Mode OTP:</span>
                                <code className="bg-white px-2 py-0.5 rounded font-black text-amber-900 text-sm shadow-sm">{init.otpDebug}</code>
                              </div>
                              <button onClick={() => setOtp(init.otpDebug || "")} className="text-[10px] font-black text-amber-900 underline uppercase tracking-widest">Auto-fill</button>
                            </div>
                          ) : null}

                          <div className="grid grid-cols-2 gap-4 pt-4">
                            <button
                              className="h-16 rounded-2xl bg-amber-900 text-sm font-black text-white shadow-xl shadow-amber-100 hover:bg-black transition-all active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-2"
                              onClick={onConfirm}
                              disabled={busy || otp.trim().length !== 6 || pin.trim().length < 4}
                            >
                              {busy ? "Verifying..." : "Confirm Payment"}
                            </button>
                            <button 
                              className="h-16 rounded-2xl border-2 border-amber-200 bg-white text-sm font-black text-amber-900 hover:bg-amber-100 transition-all active:scale-[0.98] disabled:opacity-60" 
                              onClick={onCancel} 
                              disabled={busy}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {step === "RESULT" && status ? (
                      <div className={`mt-8 rounded-3xl p-10 text-center border-4 relative overflow-hidden ${
                        status.status === "COMPLETED" || status.status === "RECOVERED" || status.status === "APPROVED" 
                          ? "bg-emerald-50 border-emerald-100" 
                          : "bg-red-50 border-red-100"
                      }`}>
                        {/* Background decor */}
                        <div className={`absolute top-0 left-0 w-full h-2 ${
                          status.status === "COMPLETED" || status.status === "RECOVERED" || status.status === "APPROVED" 
                            ? "bg-emerald-500" : "bg-red-500"
                        }`}></div>

                        <div className="text-6xl mb-6">
                          {status.status === "COMPLETED" || status.status === "RECOVERED" || status.status === "APPROVED" ? "✅" : "❌"}
                        </div>
                        
                        <h4 className={`text-2xl font-black mb-2 tracking-tight ${
                          status.status === "COMPLETED" || status.status === "RECOVERED" || status.status === "APPROVED" ? "text-emerald-900" : "text-red-900"
                        }`}>
                          {status.status === "COMPLETED" || status.status === "RECOVERED" || status.status === "APPROVED" 
                            ? "Transfer Successful" 
                            : "Transfer Failed"}
                        </h4>
                        
                        <p className="text-sm font-medium text-zinc-500 mb-8">
                          {status.status === "COMPLETED" || status.status === "RECOVERED" || status.status === "APPROVED" 
                            ? "Your payment has been processed and settled." 
                            : "Something went wrong with your transaction."}
                        </p>

                        <div className="bg-white rounded-3xl p-8 shadow-sm border border-zinc-100 mb-8 inline-block min-w-[300px]">
                          <div className="text-[10px] font-black text-zinc-400 uppercase tracking-[0.2em] mb-2">Total Amount</div>
                          <div className="text-5xl font-black text-zinc-900 tracking-tight mb-6">
                            ₹{status.amount.toLocaleString()}
                          </div>
                          <div className="pt-6 border-t border-zinc-50 flex justify-between items-center text-xs">
                            <span className="font-bold text-zinc-400">Transaction ID</span>
                            <span className="font-mono font-black text-zinc-900">{status.id.split('-')[0]}...</span>
                          </div>
                        </div>
                        
                        {status.failure_reason && (
                          <div className="mb-8 p-4 rounded-2xl bg-white border border-red-100 text-xs font-bold text-red-600 shadow-sm flex items-center justify-center gap-2">
                            <span>⚠️</span>
                            {status.failure_reason === "ROLLBACK_AFTER_MAX_RETRIES" 
                              ? "Network error. Funds have been safely returned to your account." 
                              : `Error Details: ${status.failure_reason}`}
                          </div>
                        )}
                        
                        <button 
                          onClick={onReset}
                          className="w-full h-16 rounded-2xl bg-zinc-900 text-white text-sm font-black shadow-xl hover:bg-black transition-all active:scale-[0.98]"
                        >
                          Return to Dashboard
                        </button>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="lg:col-span-5 space-y-6">
                <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
                  <div className="flex items-center justify-between mb-8">
                    <div>
                      <h3 className="text-sm font-black text-zinc-900 uppercase tracking-widest">Network Monitor</h3>
                      <p className="text-[10px] font-bold text-zinc-400 mt-0.5 uppercase tracking-widest">Real-time status</p>
                    </div>
                    <button 
                      className="h-10 px-4 rounded-xl border border-zinc-200 bg-white text-[10px] font-black uppercase tracking-widest hover:bg-zinc-50 transition-all disabled:opacity-50 shadow-sm" 
                      disabled={!txnId || busy} 
                      onClick={() => txnId && refreshStatus(txnId)}
                    >
                      Sync
                    </button>
                  </div>
                  
                  {!txnId ? (
                    <div className="py-12 text-center">
                      <div className="w-16 h-16 bg-zinc-50 rounded-3xl flex items-center justify-center text-3xl mx-auto mb-4 opacity-50 grayscale">
                        📡
                      </div>
                      <p className="text-[10px] font-black text-zinc-400 uppercase tracking-[0.2em]">Idle Mode</p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-100 flex items-center justify-between">
                        <div>
                          <span className="text-[9px] font-black text-zinc-400 uppercase tracking-widest block mb-1">State Machine</span>
                          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded-lg ${
                            status?.status === "COMPLETED" ? "bg-emerald-500 text-white" : "bg-blue-600 text-white"
                          }`}>
                            {status?.status ?? init?.status}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="text-[9px] font-black text-zinc-400 uppercase tracking-widest block mb-1">Active Txn</span>
                          <span className="font-mono text-[10px] font-black text-zinc-900">{txnId.split('-')[0]}...</span>
                        </div>
                      </div>
                      
                      {status && status.status === "APPROVED" && status.retries > 0 && (
                        <div className="flex items-center gap-3 p-4 rounded-2xl bg-amber-50 border border-amber-100 animate-pulse">
                          <div className="relative">
                            <span className="flex h-3 w-3 rounded-full bg-amber-500"></span>
                            <span className="absolute top-0 left-0 animate-ping flex h-3 w-3 rounded-full bg-amber-500 opacity-75"></span>
                          </div>
                          <span className="text-[10px] font-black text-amber-700 uppercase tracking-widest">
                            Retrying Settlement ({status.retries}/3)
                          </span>
                        </div>
                      )}

                      <div className="grid gap-4">
                        <div className="flex justify-between items-center p-3 rounded-xl bg-white border border-zinc-100">
                          <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest">Value</span>
                          <span className="font-black text-zinc-900 text-sm">₹{(status?.amount ?? Number(amount)).toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between items-center p-3 rounded-xl bg-white border border-zinc-100">
                          <span className="text-[10px] font-black text-zinc-400 uppercase tracking-widest">Decision</span>
                          <span className="font-black text-zinc-900 text-[10px] uppercase tracking-widest">{status?.decision ?? init?.decision}</span>
                        </div>
                        
                        <div className="pt-4 border-t border-zinc-100">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="w-1.5 h-1.5 bg-zinc-400 rounded-full"></span>
                            <span className="text-[9px] font-black text-zinc-400 uppercase tracking-widest">Execution Trace</span>
                          </div>
                          <div className="p-4 rounded-2xl bg-zinc-900 text-[10px] font-bold text-zinc-300 leading-relaxed font-mono">
                            {status?.decision_reason ?? (init ? init.reasons.join(" | ") : "Waiting for user authorization...")}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
                  <div className="flex items-center justify-between mb-8">
                    <div>
                      <h3 className="text-sm font-black text-zinc-900 uppercase tracking-widest">Activity Feed</h3>
                      <p className="text-[10px] font-bold text-zinc-400 mt-0.5 uppercase tracking-widest">History</p>
                    </div>
                    <button 
                      className="h-10 px-4 rounded-xl border border-zinc-200 bg-white text-[10px] font-black uppercase tracking-widest hover:bg-zinc-50 transition-all disabled:opacity-50 shadow-sm" 
                      disabled={busy} 
                      onClick={onLoadNotifications}
                    >
                      Sync
                    </button>
                  </div>
                  
                  <div className="space-y-4">
                    <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-100">
                      <span className="text-[9px] font-black text-zinc-400 uppercase tracking-widest block mb-1">Authenticated Context</span>
                      <span className="font-mono text-[10px] font-black text-zinc-400 truncate block">{notificationsUserId}</span>
                    </div>
                    
                    <div className="max-h-80 overflow-auto rounded-2xl border border-zinc-50 bg-zinc-50/50 p-3 space-y-3 custom-scrollbar">
                      {notifications.length === 0 ? (
                        <div className="py-10 text-center">
                          <p className="text-[10px] font-black text-zinc-300 uppercase tracking-[0.2em]">No Recent Activity</p>
                        </div>
                      ) : (
                        notifications.map((n) => (
                          <div key={n.id} className="p-4 rounded-xl bg-white border border-zinc-100 shadow-sm group hover:border-blue-200 transition-all">
                            <div className="flex items-center justify-between mb-2">
                              <span className={`text-[8px] font-black px-1.5 py-0.5 rounded uppercase tracking-widest ${
                                n.type === "PAYMENT_RECEIVED" ? "bg-emerald-100 text-emerald-700" :
                                n.type === "PAYMENT_SENT" ? "bg-blue-100 text-blue-700" :
                                "bg-zinc-100 text-zinc-700"
                              }`}>
                                {n.type.replace('_', ' ')}
                              </span>
                              <span className="text-[8px] font-bold text-zinc-400">{new Date(n.created_at).toLocaleTimeString()}</span>
                            </div>
                            <p className="text-[11px] font-bold text-zinc-700 leading-relaxed">{n.message}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
