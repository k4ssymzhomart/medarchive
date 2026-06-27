// Proof beat: только реальные цифры проекта. Гигантский числовой якорь (контраст
// масштаба) плюс счётчики, считающие один раз. Фоновая сетка с лёгким параллаксом.

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { Reveal } from "./Reveal";
import { Counter } from "./Counter";

const GRID_BG = {
  backgroundImage:
    "linear-gradient(rgba(10,10,11,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(10,10,11,.05) 1px, transparent 1px)",
  backgroundSize: "44px 44px",
} as const;

type Stat = { to: number; suffix?: string; label: string };

const STATS: Stat[] = [
  { to: 5, label: "формата прайсов: PDF, скан, DOCX, XLSX, XLS" },
  { to: 95, suffix: "%", label: "уверенность матча по коду тарификатора" },
  { to: 18435, label: "позиций обработано из реального архива" },
];

export function Proof() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const bgY = useTransform(scrollYProgress, [0, 1], ["-6%", "6%"]);

  return (
    <section ref={ref} className="relative overflow-hidden bg-mist py-32">
      <motion.div
        aria-hidden="true"
        style={{ ...GRID_BG, y: bgY }}
        className="pointer-events-none absolute inset-0 opacity-60"
      />
      <div className="relative mx-auto max-w-content px-6">
        <Reveal intent="statement">
          <p className="eyebrow text-accent-dark">ПРОВЕРЕНО НА РЕАЛЬНОМ АРХИВЕ</p>
        </Reveal>

        <div className="mt-10 grid grid-cols-12 items-end gap-x-6 gap-y-4">
          <Reveal intent="lead" className="col-span-12 md:col-span-7">
            <div
              style={{ fontSize: "clamp(5rem, 16vw, 12rem)" }}
              className="num -ml-1 font-semibold leading-[0.9] tracking-tight text-ink"
            >
              <Counter to={1231} />
            </div>
          </Reveal>
          <Reveal intent="sub" className="col-span-12 md:col-span-4 md:col-start-9">
            <p className="text-lg leading-relaxed text-muted">
              услуга в едином справочнике, собранном из прайсов восьми клиник
            </p>
          </Reveal>
        </div>

        <div className="mt-20 grid gap-5 sm:grid-cols-3">
          {STATS.map((s) => (
            <Reveal key={s.label} intent="sub" amount={0.5}>
              <div className="h-full rounded-panel border border-line bg-paper p-7 shadow-soft">
                <Counter
                  to={s.to}
                  suffix={s.suffix}
                  className="num text-5xl font-semibold tracking-tight text-ink"
                />
                <p className="mt-3 text-sm leading-relaxed text-muted">{s.label}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export default Proof;
