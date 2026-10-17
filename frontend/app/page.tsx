import Link from "next/link";
import { IconStore } from "@/components/Icons";

export default function Home() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-6 px-6 py-10 text-center">
      <div className="w-16 h-16 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center"><IconStore /></div>
      <div className="space-y-2 max-w-sm">
        <div className="eyebrow">Royal Stack</div>
        <h1 className="text-3xl font-semibold">Scan the code at the entrance to start</h1>
        <p className="text-muted">Your assistant knows every shelf. Ask by voice, scan as you go, pay without the queue.</p>
      </div>
      <Link href="/shop" className="btn btn-ghost">Continue a store visit</Link>
      <p className="text-sm text-muted">Shop owner? <Link href="/owner/" className="text-accent font-semibold">Register your shop or sign in</Link></p>
    </main>
  );
}
