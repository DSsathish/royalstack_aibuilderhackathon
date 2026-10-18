"use client";
import { useSyncExternalStore } from "react";
import { dismiss, snapshot, subscribe, Toast } from "@/lib/toast";

const NONE: Toast[] = [];

/** Shows the toasts raised anywhere in the app. Mounted once in the root layout. */
export default function Toaster() {
  const items = useSyncExternalStore(subscribe, snapshot, () => NONE);
  if (!items.length) return null;
  return (
    <div className="toaster" aria-live="assertive">
      {items.map((t) => (
        <div key={t.id} role={t.tone === "bad" ? "alert" : "status"} className={`toast ${t.tone === "bad" ? "toast-bad" : "toast-good"}`}>
          <span className="flex-1">{t.text}</span>
          <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="toast-close">×</button>
        </div>
      ))}
    </div>
  );
}
