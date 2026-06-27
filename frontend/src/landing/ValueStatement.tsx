// Ценностное заявление. Светлая секция с мягкой фиолетовой дымкой и дрейфующим
// свечением. Моно надзаголовок задаёт настроение.

import { Reveal } from "./Reveal";

export function ValueStatement() {
  return (
    <section id="value" className="gradient-haze relative overflow-hidden py-32">
      <div
        aria-hidden="true"
        className="glow-radial animate-drift pointer-events-none absolute right-[-8%] top-[-18%] h-[520px] w-[520px]"
      />
      <div className="relative mx-auto max-w-content px-6 text-center">
        <Reveal>
          <p className="eyebrow text-accent-dark">MEDPARTNERS ЭТО ИСТОЧНИК ПРАВДЫ О ЦЕНАХ</p>
        </Reveal>
        <Reveal delay={0.06}>
          <h2 className="text-balance mx-auto mt-6 max-w-4xl text-h2 font-semibold text-ink">
            Находите услуги быстрее, сверяйте цены увереннее.
          </h2>
        </Reveal>
        <Reveal delay={0.12}>
          <p className="text-balance mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted">
            Данные по тысячам услуг и история цен клиник. AI нормализация связывает разные
            названия одной услуги и приводит их к единому справочнику.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

export default ValueStatement;
