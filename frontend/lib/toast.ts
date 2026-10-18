/** App-wide toasts: a short message at the top of the screen that clears itself. Rendered by components/Toaster. */
export type Toast = { id: number; text: string; tone: "bad" | "good" };

const LIFE_MS = 4500;
let items: Toast[] = [];
let next = 1;
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

function push(text: string, tone: Toast["tone"]): void {
  const id = next++;
  items = [...items.filter((t) => t.text !== text), { id, text, tone }].slice(-3);   // same message twice shows once
  emit();
  setTimeout(() => dismiss(id), LIFE_MS);
}

export const toast = { error: (text: string) => push(text, "bad"), ok: (text: string) => push(text, "good") };
export function dismiss(id: number): void { items = items.filter((t) => t.id !== id); emit(); }
export function subscribe(f: () => void): () => void { subs.add(f); return () => { subs.delete(f); }; }
export function snapshot(): Toast[] { return items; }
