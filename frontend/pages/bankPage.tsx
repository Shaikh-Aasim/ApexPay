import { useEffect, useState } from "react";
import Link from "next/link";
import { createBankRegistryAccount, getBankList } from "../services/backend";

export default function BankPage() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [aadharNumber, setAadharNumber] = useState("");
  const [mobileNumber, setMobileNumber] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [ifscCode, setIfscCode] = useState("");
  const [balance, setBalance] = useState(5000);
  const [bankId, setBankId] = useState("");
  const [banks, setBanks] = useState<Array<{ id: string; name: string }>>([]);
  
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    getBankList().then(res => {
      setBanks(res.banks);
      if (res.banks.length > 0) setBankId(res.banks[0].id);
    }).catch(console.error);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      await createBankRegistryAccount({
        firstName,
        lastName,
        aadharNumber,
        mobileNumber,
        accountNumber,
        bankId,
        ifscCode,
        balance,
      });
      setMsg({ type: "success", text: "Account linked to Bank Registry successfully! You can now register on ApexPay." });
      // Reset form
      setFirstName("");
      setLastName("");
      setAadharNumber("");
      setMobileNumber("");
      setAccountNumber("");
      setIfscCode("");
    } catch (err) {
      if (err instanceof Error) {
        try {
          // Try to parse Zod error if it's JSON
          const errorData = JSON.parse(err.message);
          if (errorData.details && errorData.details.fieldErrors) {
            const fieldErrors = errorData.details.fieldErrors;
            const firstError = Object.keys(fieldErrors)[0];
            setMsg({ type: "error", text: `${firstError}: ${fieldErrors[firstError][0]}` });
          } else {
            setMsg({ type: "error", text: err.message });
          }
        } catch {
          setMsg({ type: "error", text: err.message });
        }
      } else {
        setMsg({ type: "error", text: "Failed to link account" });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col items-center py-12 px-4">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-8">
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900">Central Bank Registry</h1>
            <p className="text-sm text-zinc-500">Simulate linking your mobile to a bank account</p>
          </div>
          <Link href="/" className="text-sm text-blue-600 hover:underline font-medium">
            Back to ApexPay
          </Link>
        </div>

        {msg && (
          <div className={`mb-6 p-4 rounded-lg text-sm font-medium ${
            msg.type === "success" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"
          }`}>
            {msg.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase">First Name</label>
              <input
                required
                type="text"
                className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                value={firstName}
                onChange={e => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase">Last Name</label>
              <input
                required
                type="text"
                className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                value={lastName}
                onChange={e => setLastName(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase">Aadhar Number (12 digits)</label>
            <input
              required
              type="text"
              maxLength={12}
              className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              value={aadharNumber}
              onChange={e => setAadharNumber(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase">Mobile Number</label>
            <input
              required
              type="text"
              className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              value={mobileNumber}
              onChange={e => setMobileNumber(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase">Account Number</label>
              <input
                required
                type="text"
                className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                value={accountNumber}
                onChange={e => setAccountNumber(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-500 uppercase">IFSC Code</label>
              <input
                required
                type="text"
                placeholder="APEX0001234"
                className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                value={ifscCode}
                onChange={e => setIfscCode(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase">Bank Name</label>
            <select
              className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              value={bankId}
              onChange={e => setBankId(e.target.value)}
            >
              {banks.map(bank => (
                <option key={bank.id} value={bank.id}>{bank.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-500 uppercase">Initial Balance (INR)</label>
            <input
              required
              type="number"
              className="mt-1 w-full p-3 bg-zinc-50 border border-zinc-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              value={balance}
              onChange={e => setBalance(Number(e.target.value))}
            />
          </div>

          <button
            disabled={loading}
            type="submit"
            className="w-full bg-zinc-900 text-white p-4 rounded-lg font-bold hover:bg-black transition-colors disabled:opacity-50"
          >
            {loading ? "Linking Account..." : "Link to Central Bank"}
          </button>
        </form>
      </div>
    </div>
  );
}
