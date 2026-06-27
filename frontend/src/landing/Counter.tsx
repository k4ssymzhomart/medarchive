// Счётчик реальных чисел: считает один раз при появлении, expo-out, без оверщута
// (landing-page-craft.md). Только настоящие цифры проекта.

import { useEffect, useRef } from "react";
import { animate, useInView, useReducedMotion } from "framer-motion";
import { ease } from "../lib/motion";

export function Counter({
  to,
  from = 0,
  duration = 1.2,
  decimals = 0,
  suffix = "",
  prefix = "",
  className = "",
}: {
  to: number;
  from?: number;
  duration?: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const reduce = useReducedMotion();

  const fmt = (v: number) =>
    prefix +
    v.toLocaleString("ru-RU", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) +
    suffix;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduce) {
      el.textContent = fmt(to);
      return;
    }
    if (!inView) return;
    const controls = animate(from, to, {
      duration,
      ease: ease.out,
      onUpdate: (v) => {
        el.textContent = fmt(v);
      },
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView, reduce, to, from, duration]);

  return (
    <span ref={ref} className={className}>
      {fmt(reduce ? to : from)}
    </span>
  );
}

export default Counter;
