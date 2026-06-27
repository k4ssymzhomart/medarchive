// Hero. Светлая секция с мягким радиальным свечением акцента, которое медленно
// дрейфует (отключается при prefers-reduced-motion через CSS).

import { Reveal } from "./Reveal";
import { EmailCapture } from "./EmailCapture";

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden bg-paper">
      <div
        aria-hidden="true"
        className="glow-radial animate-drift pointer-events-none absolute left-1/2 top-[14%] h-[680px] w-[680px] -translate-x-1/2"
      />
      <div className="relative mx-auto max-w-content px-6 pb-28 pt-40 text-center">
        <Reveal>
          <p className="eyebrow text-muted">MEDPARTNERS · ЕДИНАЯ БАЗА ЦЕН КЛИНИК</p>
        </Reveal>
        <Reveal delay={0.06}>
          <h1 className="text-balance mt-6 text-display font-semibold text-ink">
            Все прайсы клиник в одной базе
          </h1>
        </Reveal>
        <Reveal delay={0.12}>
          <p className="text-balance mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted">
            Автоматически разбираем прайсы клиник партнёров, нормализуем услуги к единому
            справочнику и проверяем цены. Находите, кто оказывает услугу и по какой цене.
          </p>
        </Reveal>
        <Reveal delay={0.18}>
          <div id="demo" className="mt-9 flex justify-center">
            <EmailCapture />
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export default Hero;
