// Rest beat: одна строка, много воздуха. Пауза в музыке страницы (py крупный).

import { Reveal } from "./Reveal";

export function Statement() {
  return (
    <section className="bg-paper py-40">
      <div className="mx-auto max-w-content px-6">
        <Reveal intent="statement">
          <p className="max-w-4xl text-h2 font-semibold leading-[1.12] text-ink">
            Каждая цифра имеет происхождение: файл, страница, строка и уверенность
            сопоставления.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

export default Statement;
