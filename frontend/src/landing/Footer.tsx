// Футер (тёмный). Бренд плюс колонки ссылок. Без фейковых сертификатов.
// Ссылки ведут на разделы продукта или якоря, внешних интеграций пока нет.

import { BrandMark } from "./BrandMark";

const COLUMNS: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Компания",
    links: [
      { label: "О нас", href: "#value" },
      { label: "Команда", href: "#value" },
      { label: "Карьера", href: "#value" },
    ],
  },
  {
    title: "Ресурсы",
    links: [
      { label: "Цены", href: "#cta" },
      { label: "Документация API", href: "/app" },
      { label: "Поддержка", href: "#cta" },
    ],
  },
];

export function Footer() {
  return (
    <footer id="footer" className="bg-ink text-paper">
      <div className="mx-auto max-w-content px-6 py-20">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <BrandMark tone="paper" />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
              Единая база цен клиник партнёров. Извлечение, нормализация и проверка цен.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h4 className="text-sm font-semibold tracking-tight">{col.title}</h4>
              <ul className="mt-4 flex flex-col gap-3">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="text-sm text-muted transition-colors duration-200 hover:text-paper"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-16 flex flex-col gap-4 border-t border-surface-line pt-8 text-sm text-muted md:flex-row md:items-center md:justify-between">
          <span>Все права защищены © 2026 MedPartners</span>
          <div className="flex gap-6">
            <a href="#footer" className="transition-colors duration-200 hover:text-paper">
              Политика конфиденциальности
            </a>
            <a href="#footer" className="transition-colors duration-200 hover:text-paper">
              Условия
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
