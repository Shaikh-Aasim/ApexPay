import { useState } from "react";
import { getBalance, type BalanceResponse } from "../services/backend";

export default function CheckBalance() {
  const [vpa, setVpa] = useState("aarav@apex");
  const [result, setResult] = useState<BalanceResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onCheckBalance() {
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await getBalance(vpa.trim());
      setResult(r);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "UNKNOWN_ERROR";
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5">
      <h2 className="text-lg font-semibold">Check Balance</h2>
      
      <div className="mt-4 grid gap-3">
        <label className="grid gap-1 text-sm">
          <span className="text-zinc-700">Enter VPA</span>
          <input 
            className="h-10 rounded-xl border border-zinc-200 px-3" 
            value={vpa} 
            onChange={(e) => setVpa(e.target.value)} 
            placeholder="example@apex"
          />
        </label>

        <button
          onClick={onCheckBalance}
          disabled={busy || vpa.length < 3}
          className="h-10 rounded-xl bg-zinc-900 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Checking..." : "Check Balance"}
        </button>

        {err && (
          <div className="mt-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {err === "VPA_NOT_FOUND" ? "Invalid VPA: Not Found" : err}
          </div>
        )}

        {result && (
          <div className="mt-2 rounded-lg bg-emerald-50 p-4 text-emerald-900">
            <div className="text-xs font-medium uppercase tracking-wider text-emerald-700">Account Balance</div>
            <div className="mt-1 text-2xl font-bold">₹{result.balance.toLocaleString()}</div>
            <div className="mt-1 text-xs text-emerald-600">VPA: {result.vpa}</div>
          </div>
        )}
      </div>
    </div>
  );
}
