// Фича секция: тёмная, с акцентным свечением сверху. Глубина создаётся свечением
// акцента, а не чёрными тенями. Ниже три мини карточки преимуществ.

import { FileStack, Sparkles, History } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Reveal } from "./Reveal";

const CARDS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: FileStack,
    title: "Извлечение из любых форматов",
    body: "PDF, сканы, DOCX, XLSX и XLS. OCR для сканов.",
  },
  {
    icon: Sparkles,
    title: "Нормализация на AI",
    body: "Семантический поиск плюс код тарификатора. Высокий процент автосопоставления.",
  },
  {
    icon: History,
    title: "История цен и проверка",
    body: "Версионирование цен, детектор аномалий, очередь верификации.",
  },
];

export function FeatureSpotlight() {
  return (
    <section id="features" className="relative overflow-hidden bg-ink py-32 text-paper">
      <div
        aria-hidden="true"
        className="glow-radial animate-drift pointer-events-none absolute left-1/2 top-[-22%] h-[640px] w-[640px] -translate-x-1/2 opacity-70"
      />
      <div className="relative mx-auto max-w-content px-6">
        <div className="mx-auto max-w-3xl text-center">
          <Reveal>
            <div className="inline-flex items-center gap-2.5 rounded-pill border border-surface-line bg-surface px-4 py-2">
              <Sparkles className="h-4 w-4 text-accent-light" />
              <span className="text-sm font-medium tracking-tight">Движок нормализации</span>
            </div>
          </Reveal>
          <Reveal delay={0.06}>
            <p className="text-balance mt-7 text-h2 font-semibold leading-tight">
              AI, который приводит тысячи разных названий услуг к единому справочнику и
              мгновенно находит совпадения по коду тарификатора.
            </p>
          </Reveal>
        </div>

        <div className="mt-16 grid gap-5 md:grid-cols-3">
          {CARDS.map((c, i) => {
            const Icon = c.icon;
            return (
              <Reveal key={c.title} delay={0.08 * i}>
                <div className="h-full rounded-panel border border-surface-line bg-surface p-7 transition-transform duration-300 ease-out2 hover:-translate-y-1">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-card bg-accent/15 text-accent-light">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold">{c.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{c.body}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default FeatureSpotlight;
