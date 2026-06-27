// Подписной момент страницы (the turn): конвейер от прайса к проверенной цене.
// Закреплённая (sticky) сцена, проигрываемая скроллом: три этапа загораются по
// очереди, прогресс-линия заполняется, сигнал бежит по треку. Максимум эффекта,
// но один. Под reduced-motion и мобайл — статичная раскладка без пина.

import { useRef, useState } from "react";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  useMotionValueEvent,
  useReducedMotion,
} from "framer-motion";
import { FileStack, Sparkles, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { scrubSpring, ease } from "../lib/motion";
import { useIsDesktop } from "../lib/useMedia";

type Stage = {
  no: string;
  icon: LucideIcon;
  title: string;
  body: string;
  chips?: string[];
};

const STAGES: Stage[] = [
  {
    no: "01",
    icon: FileStack,
    title: "Извлечение",
    body: "Разбираем прайсы из любых форматов. Таблицы без линий читаем по координатам, сканы переОCR иваем.",
    chips: ["PDF", "Скан", "DOCX", "XLSX", "XLS"],
  },
  {
    no: "02",
    icon: Sparkles,
    title: "Нормализация",
    body: "Связываем разные названия одной услуги. Семантический поиск плюс матч по коду тарификатора, единый справочник из 1281 услуги.",
  },
  {
    no: "03",
    icon: ShieldCheck,
    title: "Проверка",
    body: "Версионирование цен, детектор аномалий и очередь верификации. У каждой цифры есть происхождение.",
  },
];

function StageCard({ stage, lit, current }: { stage: Stage; lit: boolean; current: boolean }) {
  const Icon = stage.icon;
  return (
    <motion.div
      animate={{ y: current ? -8 : 0, opacity: lit ? 1 : 0.45 }}
      transition={{ duration: 0.4, ease: ease.out }}
      className={[
        "flex h-full flex-col rounded-panel border bg-paper p-7 transition-colors duration-300",
        current ? "border-accent shadow-glow" : "border-line shadow-soft",
      ].join(" ")}
    >
      <div className="flex items-center justify-between">
        <span
          className={[
            "inline-flex h-12 w-12 items-center justify-center rounded-card transition-colors duration-300",
            lit ? "bg-accent text-paper" : "bg-mist text-muted",
          ].join(" ")}
        >
          <Icon className="h-6 w-6" />
        </span>
        <span className="num text-sm font-medium text-muted">{stage.no}</span>
      </div>
      <h3 className="mt-6 text-xl font-semibold text-ink">{stage.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{stage.body}</p>
      {stage.chips && (
        <div className="mt-5 flex flex-wrap gap-2">
          {stage.chips.map((c) => (
            <span
              key={c}
              className="rounded-pill border border-line px-3 py-1 text-xs font-medium text-muted"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}

function Header() {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="eyebrow text-accent-dark">КАК ЭТО РАБОТАЕТ</p>
      <h2 className="mt-4 text-h2 font-semibold text-ink">От прайса к проверенной цене</h2>
    </div>
  );
}

export function Pipeline() {
  const reduce = useReducedMotion();
  const desktop = useIsDesktop();
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const p = useSpring(scrollYProgress, scrubSpring);
  const lineWidth = useTransform(p, [0.05, 0.95], ["0%", "100%"]);
  const dotLeft = useTransform(p, [0.05, 0.95], ["0%", "100%"]);

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    const next = Math.min(STAGES.length - 1, Math.max(0, Math.floor(v * STAGES.length)));
    setActive((prev) => (prev === next ? prev : next));
  });

  // Статичная раскладка без пина: reduced-motion или мобайл.
  if (reduce || !desktop) {
    return (
      <section className="bg-paper py-24">
        <div className="mx-auto max-w-content px-6">
          <Header />
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {STAGES.map((s) => (
              <StageCard key={s.no} stage={s} lit current={false} />
            ))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section ref={ref} className="relative h-[320vh] bg-paper">
      <div className="sticky top-0 flex h-screen flex-col justify-center overflow-hidden px-6 py-20">
        <Header />
        <div className="relative mx-auto mt-14 w-full max-w-content">
          {/* трек прогресса */}
          <div className="absolute inset-x-1 top-0 h-px bg-line" />
          <motion.div style={{ width: lineWidth }} className="absolute left-1 top-0 h-[2px] bg-accent" />
          <motion.div
            style={{ left: dotLeft }}
            className="absolute top-0 -ml-2 -mt-[7px] h-4 w-4 rounded-full bg-accent shadow-glow"
          />
          <div className="grid gap-5 pt-10 md:grid-cols-3">
            {STAGES.map((s, i) => (
              <StageCard key={s.no} stage={s} lit={i <= active} current={i === active} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default Pipeline;
