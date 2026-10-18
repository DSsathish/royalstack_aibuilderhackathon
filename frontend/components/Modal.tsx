"use client";
import { useEffect } from "react";

/** A dialog over the page: Escape or the backdrop closes it, focus stays inside the card. */
export default function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-base font-semibold flex-1">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="btn btn-ghost py-1 px-2">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}
