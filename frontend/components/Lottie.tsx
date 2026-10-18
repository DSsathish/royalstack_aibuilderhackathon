"use client";
import { useEffect, useRef, useState } from "react";
import type { AnimationItem } from "lottie-web";
import { MOTION, MotionSlot, reducedMotion } from "@/lib/motion";

/** One animation slot (docs/lld/motion.md). The light Lottie player loads only when a slot with a file is on screen;
 *  the fallback shows until then, whenever the file is missing, and always under reduced motion. The animation plays
 *  only while visible and while the tab is in front; the box is fixed, so nothing shifts. */
export default function Lottie({ slot, fallback, className = "" }: { slot: MotionSlot; fallback: React.ReactNode; className?: string }) {
  const spec = MOTION[slot];
  const box = useRef<HTMLDivElement>(null);
  const anim = useRef<AnimationItem | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const el = box.current;
    if (!el || !spec.src || reducedMotion()) return;
    let stopped = false;
    let visible = false;
    const sync = () => { if (!anim.current) return; if (visible && document.visibilityState === "visible") anim.current.play(); else anim.current.pause(); };
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; sync(); }, { threshold: 0.2 });
    io.observe(el);
    document.addEventListener("visibilitychange", sync);
    import("lottie-web/build/player/lottie_light").then((mod) => {
      if (stopped) return;
      const lottie = (mod as unknown as { default: typeof import("lottie-web").default }).default ?? (mod as unknown as typeof import("lottie-web").default);
      anim.current = lottie.loadAnimation({ container: el, renderer: "svg", loop: spec.loop, autoplay: false, path: spec.src,
        rendererSettings: { progressiveLoad: true, preserveAspectRatio: "xMidYMid meet" } });
      anim.current.addEventListener("DOMLoaded", () => { setReady(true); sync(); });
      anim.current.addEventListener("data_failed", () => setReady(false));
    }).catch(() => setReady(false));
    return () => { stopped = true; io.disconnect(); document.removeEventListener("visibilitychange", sync); anim.current?.destroy(); anim.current = null; };
  }, [spec.src, spec.loop]);
  return (
    <div className={`relative inline-flex items-center justify-center ${className}`} style={{ width: spec.size, height: spec.size }} role="img" aria-label={spec.label}>
      <div ref={box} className={`absolute inset-0 ${ready ? "" : "opacity-0"}`} aria-hidden />
      {!ready && <div className="absolute inset-0 flex items-center justify-center">{fallback}</div>}
    </div>
  );
}
