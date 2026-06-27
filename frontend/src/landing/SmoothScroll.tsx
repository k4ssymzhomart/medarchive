// Плавный скролл Lenis, синхронизированный с Framer (один RAF, без двойного jitter).
// По landing-page-craft.md: не монтируем Lenis при prefers-reduced-motion и на тач/мобайл
// (нативная инерция там лучше), чтобы ничего не ломалось.

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ReactLenis } from "lenis/react";
import type { LenisRef } from "lenis/react";
import { frame, cancelFrame, useReducedMotion } from "framer-motion";

function useIsDesktop() {
  const [desktop, setDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return desktop;
}

export function SmoothScroll({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  const desktop = useIsDesktop();
  const lenisRef = useRef<LenisRef>(null);
  const enabled = !reduce && desktop;

  useEffect(() => {
    if (!enabled) return;
    function update(data: { timestamp: number }) {
      lenisRef.current?.lenis?.raf(data.timestamp);
    }
    frame.update(update, true); // keepAlive: каждый кадр
    return () => cancelFrame(update);
  }, [enabled]);

  if (!enabled) return <>{children}</>;

  return (
    <ReactLenis
      root
      ref={lenisRef}
      options={{ autoRaf: false, lerp: 0.085, smoothWheel: true, syncTouch: false }}
    >
      {children}
    </ReactLenis>
  );
}

export default SmoothScroll;
