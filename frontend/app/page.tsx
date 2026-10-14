import Link from "next/link";

export default function Home() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-6 p-6 text-center">
      <img src="/icon.svg" alt="" className="w-20 h-20" />
      <h1 className="text-2xl font-bold">Royal Stack Store Assistant</h1>
      <p className="text-zinc-500 max-w-sm">Scan the QR code at the store entrance to start shopping with the assistant. No app install needed.</p>
      <Link href="/shop" className="rounded-lg border px-4 py-2 text-sm">Continue a store session</Link>
    </main>
  );
}
