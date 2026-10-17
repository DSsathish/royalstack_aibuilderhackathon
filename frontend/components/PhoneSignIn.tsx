"use client";
import { useState } from "react";
import type { ConfirmationResult } from "firebase/auth";
import { confirmOtp, phoneUser, reverifyPhone, sendOtp } from "@/lib/firebase";
import { normaliseIndianMobile, validateIndianMobile } from "@/lib/phone";

/** Mobile number, then the one-time code. Indian numbers only for now (+91).
 *  With `reverify`, the signed-in shopper confirms a code sent to their own number (used before spending points). */
export default function PhoneSignIn({ onDone, onSkip, reverify }: { onDone: () => Promise<void> | void; onSkip?: () => void; reverify?: boolean }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [pending, setPending] = useState<ConfirmationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const digits = normaliseIndianMobile(phone);
  const phoneProblem = phone.trim() ? validateIndianMobile(digits) : "";
  const full = reverify ? (phoneUser()?.phoneNumber ?? "") : "+91" + digits;
  const codeDigits = code.replace(/\D/g, "");

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
              <input value={phone} onChange={(e) => { setPhone(e.target.value); setError(""); }} inputMode="tel" autoComplete="tel-national" placeholder="98765 43210" maxLength={16}
                aria-invalid={!!phoneProblem} className={`field ${phoneProblem ? "border-bad" : ""}`} />
            </div>
            {phoneProblem ? <span className="block text-xs text-bad mt-1">{phoneProblem}</span> : digits.length === 10 ? <span className="block text-xs text-muted mt-1">We will send a code to +91 {digits.slice(0, 5)} {digits.slice(5)}</span> : <span className="block text-xs text-muted mt-1">10-digit Indian mobile number, with or without +91.</span>}
          </label>
          <div className="flex gap-2">
            <button onClick={send} disabled={busy || !!phoneProblem || digits.length !== 10} className="btn btn-primary">{busy ? "Sending" : "Send code"}</button>
            {onSkip && <button onClick={onSkip} className="btn btn-ghost">Skip for now</button>}
          </div>
        </>
      ) : (
        <>
          <label className="block text-sm font-medium">Code sent to {reverify ? "your number ending in " + full.slice(-4) : full}
            <input value={code} onChange={(e) => { setCode(e.target.value.replace(/\D/g, "").slice(0, 6)); setError(""); }} inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code" maxLength={6} className="field mt-1 mono tracking-widest" />
            <span className="block text-xs text-muted mt-1">{codeDigits.length}/6 digits</span>
          </label>
          <div className="flex gap-2">
            <button onClick={confirm} disabled={busy || codeDigits.length !== 6} className="btn btn-primary">{busy ? "Checking" : "Verify"}</button>
            <button onClick={() => { setPending(null); setCode(""); }} className="btn btn-ghost">{reverify ? "Back" : "Change number"}</button>
          </div>
        </>
      )}
      {error && <p className="chip chip-bad whitespace-normal">{error}</p>}
      <div id="recaptcha-slot" />
      <p className="text-[11px] text-muted leading-snug">This form is protected by reCAPTCHA; the Google <a href="https://policies.google.com/privacy" className="underline" target="_blank" rel="noreferrer">Privacy Policy</a> and <a href="https://policies.google.com/terms" className="underline" target="_blank" rel="noreferrer">Terms of Service</a> apply.</p>
    </div>
  );
}
