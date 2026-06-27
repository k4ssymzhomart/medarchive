// Скромный баннер согласия на cookie. Оригинальный текст. Без localStorage:
// решение хранится только в состоянии компонента на время сессии страницы.

import { useState } from "react";

export function CookieConsent() {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 max-w-xs rounded-card border border-line bg-paper p-5 shadow-lift">
      <p className="text-sm leading-relaxed text-muted">
        Мы используем cookie для аналитики.
      </p>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="rounded-pill bg-ink px-4 py-2 text-sm font-medium text-paper transition-transform duration-200 ease-out2 hover:scale-[1.03]"
        >
          Принять
        </button>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="rounded-pill border border-line px-4 py-2 text-sm font-medium text-ink transition-colors duration-200 hover:bg-mist"
        >
          Отклонить
        </button>
      </div>
    </div>
  );
}

export default CookieConsent;
