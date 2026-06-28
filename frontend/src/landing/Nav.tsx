// Sticky навигация. При скролле вниз ужимается в плавающую пилюлю по центру,
// логотип сворачивается, фон становится полупрозрачным с блюром.

import { useEffect, useState } from "react";
import { BrandMark } from "./BrandMark";

const LINKS = [
  { label: "Возможности", href: "#features" },
  { label: "Как это работает", href: "#pipeline" },
  { label: "Результаты", href: "#metrics" },
  { label: "Компания", href: "#footer" },
];

export function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 64);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4">
      <nav
        className={[
          "flex items-center gap-3 transition-all duration-300 ease-out2",
          scrolled
            ? "rounded-pill border border-line/70 bg-paper/85 px-3 py-2 shadow-soft backdrop-blur-md"
            : "w-full max-w-content rounded-pill bg-transparent px-1 py-2",
        ].join(" ")}
      >
        <a
          href="#top"
          aria-label="MedServicePrice, наверх"
          className={[
            "overflow-hidden transition-all duration-300 ease-out2",
            scrolled ? "max-w-0 opacity-0" : "max-w-[240px] opacity-100",
          ].join(" ")}
        >
          <BrandMark />
        </a>

        <div className="mx-auto hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-pill px-3.5 py-2 text-sm text-muted transition-colors duration-200 hover:bg-mist hover:text-ink"
            >
              {l.label}
            </a>
          ))}
        </div>

        <a
          href="#cta"
          className="ml-auto inline-flex items-center rounded-pill bg-ink px-4 py-2 text-sm font-medium text-paper transition-transform duration-200 ease-out2 hover:scale-[1.03]"
        >
          Запросить демо
        </a>
      </nav>
    </header>
  );
}

export default Nav;
