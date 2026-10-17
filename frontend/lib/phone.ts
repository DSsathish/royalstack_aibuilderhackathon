/** Indian mobile number helpers, free of React and Firebase so they can be unit-tested. */

/** Accepts "98765 43210", "+91 98765 43210", "091…", "9198765…"; returns the 10 subscriber digits. */
export function normaliseIndianMobile(raw: string): string {
  let d = raw.replace(/\D/g, "");
  if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
  if (d.length === 11 && d.startsWith("0")) d = d.slice(1);
  return d;
}

/** "" when valid; otherwise what to fix. Indian mobile numbers are ten digits and start with 6, 7, 8 or 9. */
export function validateIndianMobile(digits: string): string {
  if (!digits) return "";
  if (!/^\d+$/.test(digits)) return "Digits only, please.";
  if (digits.length < 10) return `${10 - digits.length} more digit${10 - digits.length === 1 ? "" : "s"} needed.`;
  if (digits.length > 10) return "That is more than 10 digits. Enter the mobile number without the country code.";
  if (!/^[6-9]/.test(digits)) return "Indian mobile numbers start with 6, 7, 8 or 9.";
  if (/^(\d)\1{9}$/.test(digits)) return "That does not look like a real number.";
  return "";
}

export function friendlyAuthError(e: unknown): string {
  const m = (e as Error)?.message ?? "";
  if (m.includes("invalid-verification-code")) return "That code is not right. Check and try again.";
  if (m.includes("code-expired")) return "That code has expired. Send a new one.";
  if (m.includes("too-many-requests")) return "Too many attempts. Please wait a few minutes.";
  if (m.includes("invalid-phone-number")) return "Enter a valid 10-digit mobile number.";
  if (m.includes("operation-not-allowed")) return "Text messages cannot be sent to this number's region right now. You can skip sign-in and continue shopping.";
  if (m.includes("captcha-check-failed") || m.includes("invalid-app-credential") || m.includes("missing-app-credential")) return "The security check did not complete. Reload the page and try again.";
  if (m.includes("quota-exceeded")) return "Too many codes were sent today. Please try again later or skip sign-in.";
  if (m.includes("network-request-failed")) return "No connection. Check your network and try again.";
  return "Could not sign in. Please try again.";
}
