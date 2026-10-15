"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";

/** The exit QR links here; a shopper who opens it just sees the code again to show at the kiosk. */
function ExitCode() {
  const token = useSearchParams().get("r") ?? "";
  if (!token) return <main className="p-6 text-center text-zinc-500">No receipt code.</main>;
  const url = `${typeof window !== "undefined" ? window.location.origin : ""}/exit/?r=${token}`;
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="eyebrow">Exit pass</div>
      <h1 className="text-2xl font-semibold">Show this at the exit</h1>
      <div className="bg-white p-3 rounded-[14px]"><QRCodeSVG value={url} size={240} /></div>
      <p className="text-sm text-muted">The exit kiosk scans this code. It expires 30 minutes after payment.</p>
    </main>
  );
}
export default function Page() { return <Suspense><ExitCode /></Suspense>; }
