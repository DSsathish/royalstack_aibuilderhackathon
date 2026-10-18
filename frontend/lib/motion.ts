/** The motion registry (docs/lld/motion.md): one slot per moment. An empty `src` means the slot shows its fallback,
 *  so nothing changes until an animation is chosen through LottieFiles and saved under public/motion/. */
export type MotionSlot = "hero" | "loading" | "noResults" | "emptyCart" | "orderPlaced";

export const MOTION: Record<MotionSlot, { src: string; loop: boolean; size: number; label: string }> = {
  hero: { src: "", loop: true, size: 160, label: "A shop with an assistant" },
  loading: { src: "", loop: true, size: 96, label: "Loading the shop" },
  noResults: { src: "", loop: false, size: 120, label: "Nothing matched" },
  emptyCart: { src: "", loop: false, size: 120, label: "Your cart is empty" },
  orderPlaced: { src: "", loop: false, size: 140, label: "Order placed" },
};

/** True when the person asked the system for less motion: every slot then shows its fallback. */
export function reducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}
