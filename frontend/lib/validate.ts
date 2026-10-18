/** Form checks shared by every page: required fields, then a rule per field. Errors show in red under each field and
 *  as one toast, so an empty mandatory field never fails silently. */
import { toast } from "./toast";

export type Errors = Record<string, string>;
export type Field = {
  label: string;
  value: unknown;
  rule?: (v: string) => string;   // "" when fine
  optional?: boolean;             // blank is fine; the rule runs only when filled in
  missing?: string;               // message when blank, instead of "<label> is required."
};

export const blank = (v: unknown): boolean =>
  v === null || v === undefined || (typeof v === "string" && v.trim() === "") || (typeof v === "number" && Number.isNaN(v));

export const isEmail = (v: string): boolean => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

export const rules = {
  email: (v: string) => (isEmail(v) ? "" : "Enter a valid email address."),
  minLen: (n: number, label: string) => (v: string) => (v.trim().length >= n ? "" : `${label} needs at least ${n} characters.`),
  https: (v: string) => (/^https:\/\/[^\s]+\.[^\s]+/.test(v.trim()) ? "" : "Enter a link that starts with https://"),
  number: (label: string, { min = 0, max = Infinity, integer = false, nonZero = false } = {}) => (v: string) => {
    const n = Number(v.trim());
    if (v.trim() === "" || Number.isNaN(n)) return `${label} must be a number.`;
    if (integer && !Number.isInteger(n)) return `${label} must be a whole number.`;
    if (nonZero && n === 0) return `${label} cannot be zero.`;
    if (n < min) return `${label} must be at least ${min}.`;
    if (n > max) return `${label} must be at most ${max}.`;
    return "";
  },
};

export function validate(fields: Record<string, Field>): Errors {
  const out: Errors = {};
  for (const [key, f] of Object.entries(fields)) {
    if (blank(f.value)) { if (!f.optional) out[key] = f.missing ?? `${f.label} is required.`; continue; }
    const problem = f.rule ? f.rule(String(f.value)) : "";
    if (problem) out[key] = problem;
  }
  return out;
}

/** One line for the toast: the single problem, or the fields that need attention. */
export function summary(errors: Errors, fields: Record<string, Field>): string {
  const keys = Object.keys(errors);
  if (keys.length === 1) return errors[keys[0]];
  return `Please check: ${keys.map((k) => fields[k].label).join(", ")}.`;
}

/** Validates, puts the messages under the fields and in a toast. True when the form can be submitted. */
export function guard(fields: Record<string, Field>, setErrors: (e: Errors) => void): boolean {
  const errors = validate(fields);
  setErrors(errors);
  if (Object.keys(errors).length) toast.error(summary(errors, fields));
  return Object.keys(errors).length === 0;
}
