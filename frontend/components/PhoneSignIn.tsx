"use client";
import { useState } from "react";
import type { ConfirmationResult } from "firebase/auth";
import { confirmOtp, phoneUser, reverifyPhone, sendOtp } from "@/lib/firebase";

/** Mobile number, then the one-time code. Indian numbers only for now (+91).
 *  With `reverify`, the signed-in shopper confirms a code sent to their own number (used before spending points). */
export default function PhoneSignIn({ onDone, onSkip, reverify }: { onDone: () => Promise<void> | void; onSkip?: () => void; reverify?: boolean }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [pending, setPending] = useState<ConfirmationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const digits = phone.replace(/\D/g, "");
  const full = reverify ? (phoneUser()?.phoneNumber ?? "") : "+91" + digits;

  async function send() {
    setBusy(true); setError("");
    try { setPending(reverify ? await reverifyPhone("recaptcha-slot") : await sendOtp(full, "recaptcha-slot")); } catch (e) { setError(friendly(e)); }
    setBusy(false);
  }
  async function confirm() {
    if (!pending) return;
    setBusy(true); setError("");
    try { await confirmOtp(pending, code.trim()); await onDone(); } catch (e) { setError(friendly(e)); setBusy(false); }
  }
  return (
    <div className="space-y-3">
      {!pending && reverify ? (
        <>
          <p className="text-sm text-muted">We will send a code to your number ending in {full.slice(-4)} to confirm it is you.</p>
          <div className="flex gap-2">
            <button onClick={send} disabled={busy} className="btn btn-primary">{busy ? "Sending" : "Send code"}</button>
            {onSkip && <button onClick={onSkip} className="btn btn-ghost">Cancel</button>}
          </div>
        </>
      ) : !pending ? (
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
          <label className="block text-sm font-medium">Code sent to {reverify ? "your number ending in " + full.slice(-4) : full}
            <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code" className="field mt-1 mono tracking-widest" />
          </label>
          <div className="flex gap-2">
            <button onClick={confirm} disabled={busy || code.trim().length < 6} className="btn btn-primary">{busy ? "Checking" : "Verify"}</button>
            <button onClick={() => { setPending(null); setCode(""); }} className="btn btn-ghost">{reverify ? "Back" : "Change number"}</button>
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
