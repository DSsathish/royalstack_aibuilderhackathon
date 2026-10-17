"use client";
/** Firebase web app: Google sign-in for owners and staff, phone OTP for shoppers who opt in. */
import { getApps, initializeApp } from "firebase/app";
import { ConfirmationResult, GoogleAuthProvider, RecaptchaVerifier, getAuth, onAuthStateChanged, reauthenticateWithPhoneNumber, signInWithPhoneNumber, signInWithPopup, signOut, type User } from "firebase/auth";

const config = {
  apiKey: "AIzaSyD1gsb4UoNpjbCQcyu0gLp6MNwpjxtiXsk",
  authDomain: "royastacxk-aibuildercup.firebaseapp.com",
  projectId: "royastacxk-aibuildercup",
  appId: "1:881917398995:web:046827a8f99328b25e2926",
};

function app() { return getApps()[0] ?? initializeApp(config); }
export function auth() { return getAuth(app()); }
export function signInWithGoogle() { return signInWithPopup(auth(), new GoogleAuthProvider()); }
export function signOutOwner() { return signOut(auth()); }
export const signOutShopper = signOutOwner;
export function watchUser(cb: (u: User | null) => void) { return onAuthStateChanged(auth(), cb); }
export async function idToken(): Promise<string | null> { return (await auth().currentUser?.getIdToken()) ?? null; }
/** Resolves once Firebase has restored any persisted sign-in, so a page can tell "signed out" from "not loaded yet". */
export function firstAuthState(): Promise<User | null> {
  return new Promise((resolve) => { const off = onAuthStateChanged(auth(), (u) => { off(); resolve(u); }); });
}
/** The signed-in shopper, if the current Firebase user came from phone sign-in. */
export function phoneUser(): User | null { const u = auth().currentUser; return u?.phoneNumber ? u : null; }

/** One invisible reCAPTCHA per attempt, mounted in `containerId` and removed afterwards, so pages can mount their own slot. */
async function withVerifier<T>(containerId: string, fn: (v: RecaptchaVerifier) => Promise<T>): Promise<T> {
  const v = new RecaptchaVerifier(auth(), containerId, { size: "invisible" });
  try { return await fn(v); } finally { v.clear(); }
}
/** Send a one-time code to sign in. */
export function sendOtp(phone: string, containerId: string): Promise<ConfirmationResult> {
  return withVerifier(containerId, (v) => signInWithPhoneNumber(auth(), phone, v));
}
/** Send a one-time code to the signed-in shopper's own number (the check before spending points). */
export function reverifyPhone(containerId: string): Promise<ConfirmationResult> {
  const u = phoneUser();
  if (!u?.phoneNumber) return Promise.reject(new Error("not signed in by phone"));
  return withVerifier(containerId, (v) => reauthenticateWithPhoneNumber(u, u.phoneNumber!, v));
}
export function confirmOtp(result: ConfirmationResult, code: string) { return result.confirm(code); }
/** A token minted now, so the server sees the fresh verification time. */
export async function freshIdToken(): Promise<string | null> { return (await auth().currentUser?.getIdToken(true)) ?? null; }
