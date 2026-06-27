// Финальный CTA: акцентная градиентная панель. Захват email на панели.

import { Reveal } from "./Reveal";
import { EmailCapture } from "./EmailCapture";

export function FinalCTA() {
  return (
    <section id="cta" className="bg-paper px-6 py-24">
      <div className="mx-auto max-w-content">
        <Reveal>
          <div className="gradient-cta relative overflow-hidden rounded-panel px-8 py-20 text-center shadow-glow">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute left-1/2 top-[-30%] h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-accent-light/30 blur-3xl"
            />
            <div className="relative mx-auto max-w-2xl">
              <h2 className="text-balance text-h2 font-semibold text-paper">Попробуйте MedPartners</h2>
              <p className="mt-3 text-lg text-paper/85">Запишитесь на демо сегодня</p>
              <div className="mt-8 flex justify-center">
                <EmailCapture variant="onAccent" />
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export default FinalCTA;
