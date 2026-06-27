// Финальный CTA: акцентная градиентная панель. Магнитная кнопка (единственный
// магнитный элемент на странице, радиус ~120px, сдвиг до 10px) плюс захват email.

import { useRef } from "react";
import type { ReactNode, MouseEvent } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { EmailCapture } from "./EmailCapture";
import { Reveal } from "./Reveal";

function MagneticLink({
  href,
  children,
  className = "",
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLAnchorElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 150, damping: 15, mass: 0.1 });
  const sy = useSpring(y, { stiffness: 150, damping: 15, mass: 0.1 });

  function onMove(e: MouseEvent<HTMLAnchorElement>) {
    if (reduce || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width / 2);
    const dy = e.clientY - (r.top + r.height / 2);
    const radius = 120;
    if (Math.hypot(dx, dy) < radius) {
      x.set((dx / radius) * 10);
      y.set((dy / radius) * 10);
    }
  }
  function reset() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.a
      ref={ref}
      href={href}
      style={{ x: sx, y: sy }}
      onMouseMove={onMove}
      onMouseLeave={reset}
      className={className}
    >
      {children}
    </motion.a>
  );
}

export function CTA() {
  return (
    <section id="cta" className="bg-paper px-6 py-24">
      <div className="mx-auto max-w-content">
        <Reveal intent="statement">
          <div className="gradient-cta relative overflow-hidden rounded-panel px-8 py-20 text-center shadow-glow">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute left-1/2 top-[-30%] h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-accent-light/30 blur-3xl"
            />
            <div className="relative mx-auto max-w-2xl">
              <h2 className="text-h2 font-semibold text-paper">Попробуйте MedPartners</h2>
              <p className="mt-3 text-lg text-paper/85">Запишитесь на демо сегодня</p>
              <div className="mt-8 flex justify-center">
                <EmailCapture variant="onAccent" />
              </div>
              <div className="mt-8">
                <MagneticLink
                  href="/app"
                  className="inline-flex items-center gap-2 rounded-pill border border-paper/40 px-6 py-3 text-sm font-medium text-paper transition-colors duration-200 hover:bg-paper/10"
                >
                  Открыть приложение
                  <ArrowUpRight className="h-4 w-4" />
                </MagneticLink>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export default CTA;
