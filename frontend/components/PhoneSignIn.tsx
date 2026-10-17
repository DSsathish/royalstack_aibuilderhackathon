"use client";
import { useState } from "react";
import type { ConfirmationResult } from "firebase/auth";
import { confirmOtp, sendOtp } from "@/lib/firebase";

/** Mobile number, then the one-time code. Indian numbers only for now (+91). */
export default function PhoneSignIn({ onDone, onSkip }: { onDone: () => Promise<void> | void; onSkip?: () => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [pending, setPending] = useState<ConfirmationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const digits = phone.replace(/\D/g, "");
  const full = "+91" + digits;

  async function send() {
    setBusy(true); setError("");
    try { setPending(await sendOtp(full, "recaptcha-slot")); } catch (e) { setError(friendly(e)); }
    setBusy(false);
  }
  async function confirm() {
    if (!pending) return;
    setBusy(true); setError("");
    try { await confirmOtp(pending, code.trim()); await onDone(); } catch (e) { setError(friendly(e)); setBusy(false); }
  }
  return (
    <div className="space-y-3">
      {!pending ? (
        <>
          <label className="block text-sm font-medium">Mobile number
            <div className="flex gap-2 mt-1">
              <span className="field w-auto text-muted select-none">+91</span>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel-national" placeholder="98765 43210" className="field" />
            </div>
          </label>
          <div className="flex gap-2">
            <button onClick={send} disabled={busy || digits.length !== 10} className="btn btn-primary">{busy ? "Sending" : "Send code"}</button>
            {onSkip && <button onClick={onSkip} className="btn btn-ghost">Skip for now</button>}
          </div>
        </>
      ) : (
        <>
          <label className="block text-sm font-medium">Code sent to {full}
            <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code" className="field mt-1 mono tracking-widest" />
          </label>
          <div className="flex gap-2">
            <button onClick={confirm} disabled={busy || code.trim().length < 6} className="btn btn-primary">{busy ? "Checking" : "Verify"}</button>
            <button onClick={() => { setPending(null); setCode(""); }} className="btn btn-ghost">Change number</button>
          </div>
        </>
      )}
      {error && <p className="chip chip-bad">{error}</p>}
      <div id="recaptcha-slot" />
    </div>
  );
}

function friendly(e: unknown): string {
  const m = (e as Error)?.message ?? "";
  if (m.includes("invalid-verification-code")) return "That code is not right. Check and try again.";
  if (m.includes("code-expired")) return "That code has expired. Send a new one.";
  if (m.includes("too-many-requests")) return "Too many attempts. Please wait a few minutes.";
  if (m.includes("invalid-phone-number")) return "Enter a valid 10-digit mobile number.";
  if (m.includes("operation-not-allowed")) return "Phone sign-in is not enabled for this store yet.";
  return "Could not sign in. Please try again.";
}
