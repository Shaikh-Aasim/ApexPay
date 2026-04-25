import { useState } from "react";
import { getBalance, type BalanceResponse } from "../services/backend";

export default function CheckBalance() {
  const [pin, setPin] = useState("");
  const [result, setResult] = useState<BalanceResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onCheckBalance() {
    if (pin.length < 4) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await getBalance(undefined, pin);
      setResult(r);
      setPin(""); // Clear pin after success
    } catch (e) {
      const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
      setErr(msg === "INVALID_PIN" ? "Incorrect Secure PIN" : msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center text-emerald-600 text-xl font-bold">
          💰
        </div>
        <div>
          <h3 className="text-lg font-black text-zinc-900">Check Account Balance</h3>
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Secure Access Required</p>
        </div>
      </div>
      
      <div className="grid gap-6">
        {!result ? (
          <>
            <div className="space-y-4">
              <label className="grid gap-2 text-sm">
                <span className="text-xs font-black text-zinc-700 uppercase tracking-widest">Enter Secure PIN</span>
                <input 
                  type="password"
                  className="h-14 w-full rounded-2xl border border-zinc-200 bg-zinc-50 px-4 text-center text-3xl font-black tracking-[0.5em] outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all placeholder:tracking-normal placeholder:text-sm placeholder:font-medium" 
                  value={pin} 
                  onChange={(e) => setPin(e.target.value)} 
                  placeholder="••••"
                  maxLength={6}
                />
              </label>

              <div className="rounded-xl bg-blue-50 p-4 border border-blue-100 flex gap-3">
                <span className="text-blue-600 text-lg">ℹ️</span>
                <p className="text-[11px] font-bold text-blue-700 leading-relaxed">
                  For security reasons, your account balance is only visible after PIN verification. This check is performed directly on your primary linked account.
                </p>
              </div>
            </div>

            <button
              onClick={onCheckBalance}
              disabled={busy || pin.length < 4}
              className="h-14 rounded-2xl bg-zinc-900 text-sm font-black text-white shadow-xl hover:bg-black transition-all active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {busy ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  Verifying...
                </>
              ) : (
                "View Balance Securely"
              )}
            </button>
          </>
        ) : (
          <div className="space-y-6">
            <div className="rounded-3xl bg-gradient-to-br from-emerald-500 to-teal-600 p-8 text-white shadow-xl shadow-emerald-100 relative overflow-hidden">
              {/* Decorative elements */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -mr-16 -mt-16 blur-2xl"></div>
              <div className="absolute bottom-0 left-0 w-24 h-24 bg-black/5 rounded-full -ml-12 -mb-12 blur-xl"></div>
              
              <div className="relative z-10">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-100 mb-1">Available Balance</div>
                    <div className="text-4xl font-black tracking-tight">₹{result.balance.toLocaleString()}</div>
                  </div>
                  <div className="bg-white/20 backdrop-blur-md px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest border border-white/20">
                    Active
                  </div>
                </div>
                
                <div className="pt-6 border-t border-white/20 flex justify-between items-end">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-100 mb-1">Primary VPA</div>
                    <div className="font-mono text-sm font-bold">{result.vpa}</div>
                  </div>
                  <button 
                    onClick={() => setResult(null)}
                    className="h-9 px-4 rounded-xl bg-white text-emerald-600 text-[10px] font-black uppercase tracking-widest hover:bg-emerald-50 transition-colors shadow-lg"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Real-time sync complete</span>
              </div>
              <span className="text-[10px] font-bold text-zinc-400 italic">Updated just now</span>
            </div>
          </div>
        )}

        {err && (
          <div className="mt-2 rounded-2xl bg-red-50 border border-red-100 p-4 text-xs font-bold text-red-700 flex items-center gap-3">
            <span className="text-lg">⚠️</span>
            {err}
          </div>
        )}
      </div>
    </div>
  );
}
