"use client";
/** Firebase web app: Google sign-in for owners and staff, phone OTP for shoppers who opt in. */
import { getApps, initializeApp } from "firebase/app";
import { ConfirmationResult, GoogleAuthProvider, RecaptchaVerifier, createUserWithEmailAndPassword, EmailAuthProvider, getAuth, linkWithCredential, reauthenticateWithCredential, reauthenticateWithPopup, updatePassword, verifyBeforeUpdateEmail, onAuthStateChanged, reauthenticateWithPhoneNumber, sendEmailVerification, sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPhoneNumber, signInWithPopup, signOut, type User } from "firebase/auth";

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
/** Email and password for owners and staff. A new account gets a verification link; the API accepts the email only once verified. */
export function signInWithEmail(email: string, password: string) { return signInWithEmailAndPassword(auth(), email.trim(), password); }
/** The verification page Firebase shows gets a "Continue" button back to the dashboard. */
const backToDashboard = () => ({ url: `${window.location.origin}/owner/` });
export async function createOwnerAccount(email: string, password: string) {
  const cred = await createUserWithEmailAndPassword(auth(), email.trim(), password);
  await sendEmailVerification(cred.user, backToDashboard());
  return cred.user;
}
export function resendVerification() { const u = auth().currentUser; return u ? sendEmailVerification(u, backToDashboard()) : Promise.resolve(); }
export function resetPassword(email: string) { return sendPasswordResetEmail(auth(), email.trim()); }
/** Re-read the user after they clicked the link, and mint a token that carries email_verified. */
export async function refreshVerified(): Promise<boolean> {
  const u = auth().currentUser;
  if (!u) return false;
  await u.reload();
  await u.getIdToken(true);
  return u.emailVerified;
}
export function isPasswordUser(u: User): boolean { return u.providerData.some((p) => p.providerId === "password"); }
/** Account changes (docs/lld/owner-account.md) re-authenticate first: the current password, or the Google popup. */
async function reauthenticate(currentPassword = ""): Promise<User> {
  const u = auth().currentUser;
  if (!u?.email) throw new Error("auth/not-signed-in");
  if (isPasswordUser(u)) await reauthenticateWithCredential(u, EmailAuthProvider.credential(u.email, currentPassword));
  else await reauthenticateWithPopup(u, new GoogleAuthProvider());
  return u;
}
/** A link goes to the new address; the email switches only when it is opened, so a typo cannot lock the owner out. */
export async function changeEmail(newEmail: string, currentPassword: string) {
  const u = await reauthenticate(currentPassword);
  await verifyBeforeUpdateEmail(u, newEmail.trim(), backToDashboard());
}
export async function changePassword(currentPassword: string, newPassword: string) {
  const u = await reauthenticate(currentPassword);
  await updatePassword(u, newPassword);
}
/** A Google account gains email-and-password sign-in on the same account. */
export async function addPassword(newPassword: string) {
  const u = await reauthenticate();
  await linkWithCredential(u, EmailAuthProvider.credential(u.email!, newPassword));
}
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
