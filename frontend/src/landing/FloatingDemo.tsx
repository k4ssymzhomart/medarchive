// Плавающая пилюля внизу по центру. Ведёт к захвату email. Появляется плавно
// после небольшого скролла, уважает prefers-reduced-motion.

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, CalendarClock } from "lucide-react";

export function FloatingDemo() {
  const reduce = useReducedMotion();
  const [show, setShow] = useState(false);

  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 520);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.a
      href="#demo"
      initial={false}
      animate={
        reduce
          ? { opacity: show ? 1 : 0 }
          : { opacity: show ? 1 : 0, y: show ? 0 : 16 }
      }
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      style={{ pointerEvents: show ? "auto" : "none" }}
      className="fixed bottom-6 left-1/2 z-40 inline-flex -translate-x-1/2 items-center gap-3 rounded-pill bg-ink px-5 py-3 text-paper shadow-lift"
    >
      <CalendarClock className="h-5 w-5 text-accent-light" />
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-medium">Запросить демо</span>
        <span className="text-xs text-muted">30 минут</span>
      </span>
      <ArrowUpRight className="h-4 w-4" />
    </motion.a>
  );
}

export default FloatingDemo;
