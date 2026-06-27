// Tension beat: тёмный, плотный, быстрый. Заголовок раскрывается построчно
// из-под маски (split-text по строкам, не по буквам). Контраст ритма к светлому
// hero и features.

import { motion, useReducedMotion } from "framer-motion";
import { ease } from "../lib/motion";

const LINES = [
  "Прайсы клиник живут",
  "в PDF, сканах и Excel.",
  "Разные названия, форматы и годы.",
];

export function Tension() {
  const reduce = useReducedMotion();

  return (
    <section className="relative overflow-hidden bg-ink py-28 text-paper">
      <div
        aria-hidden="true"
        className="glow-radial pointer-events-none absolute -right-20 top-1/2 h-[420px] w-[420px] -translate-y-1/2 opacity-50"
      />
      <div className="relative mx-auto max-w-content px-6">
        <p className="eyebrow text-accent-light">ПРОБЛЕМА</p>
        <h2 className="mt-6 max-w-4xl text-h2 font-semibold leading-[1.08]">
          {LINES.map((line, i) =>
            reduce ? (
              <span key={i} className="block">
                {line}
              </span>
            ) : (
              <span key={i} className="block overflow-hidden pb-[0.08em]">
                <motion.span
                  className="block"
                  initial={{ y: "110%" }}
                  whileInView={{ y: 0 }}
                  viewport={{ once: true, amount: 0.6 }}
                  transition={{ duration: 0.7, ease: ease.out, delay: i * 0.08 }}
                >
                  {line}
                </motion.span>
              </span>
            ),
          )}
        </h2>
        <p className="mt-8 max-w-xl text-lg leading-relaxed text-muted">
          Одна услуга у одной клиники называется десятком способов. Сравнить цены вручную
          невозможно. MedPartners приводит этот хаос к единому справочнику.
        </p>
      </div>
    </section>
  );
}

export default Tension;
