"use client";
/** Firebase web app for owner sign-in only. Shoppers never sign in. */
import { getApps, initializeApp } from "firebase/app";
import { GoogleAuthProvider, getAuth, onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";

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
export function watchUser(cb: (u: User | null) => void) { return onAuthStateChanged(auth(), cb); }
export async function idToken(): Promise<string | null> { return (await auth().currentUser?.getIdToken()) ?? null; }
