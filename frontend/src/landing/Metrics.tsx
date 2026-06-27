// Метрики и отзыв. Только честные реальные показатели проекта. Отзыв — нейтральный
// плейсхолдер без приписывания реальным лицам или компаниям.

import { Quote } from "lucide-react";
import { Reveal } from "./Reveal";

const METRICS: { figure: string; label: string }[] = [
  { figure: "Тысячи", label: "позиций обработано из реального архива прайсов" },
  { figure: "1281", label: "услуга в едином справочнике" },
  { figure: "выше 95%", label: "уверенность сопоставления по коду тарификатора" },
];

export function Metrics() {
  return (
    <section id="metrics" className="bg-paper py-32">
      <div className="mx-auto max-w-content px-6">
        <div className="grid gap-5 md:grid-cols-3">
          {METRICS.map((m, i) => (
            <Reveal key={m.label} delay={0.07 * i}>
              <div className="h-full rounded-panel border border-line bg-mist p-8 shadow-soft">
                <div className="num text-h2 font-semibold tracking-tight text-ink">{m.figure}</div>
                <p className="mt-3 text-sm leading-relaxed text-muted">{m.label}</p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.1}>
          <figure className="mx-auto mt-16 max-w-3xl text-center">
            <Quote className="mx-auto h-8 w-8 text-accent" />
            <blockquote className="text-balance mt-6 text-2xl font-medium leading-snug text-ink">
              [отзыв пилотной клиники]
            </blockquote>
            <figcaption className="mt-5 text-sm text-muted">
              Пилотная клиника, по итогам пилота
            </figcaption>
          </figure>
        </Reveal>
      </div>
    </section>
  );
}

export default Metrics;
