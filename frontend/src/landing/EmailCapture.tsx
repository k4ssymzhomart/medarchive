// Захват рабочего email в единой пилюле. Валидация и состояние успеха на клиенте.
// TODO: интеграция отправки на бэкенд (сейчас заглушка отправки).

import { useState, type FormEvent } from "react";
import { ArrowRight, Check } from "lucide-react";

type Variant = "light" | "onAccent";

export function EmailCapture({
  variant = "light",
  buttonLabel = "Запросить демо",
  className = "",
}: {
  variant?: Variant;
  buttonLabel?: string;
  className?: string;
}) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "error" | "success">("idle");

  function submit(e: FormEvent) {
    e.preventDefault();
    const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
    if (!ok) {
      setStatus("error");
      return;
    }
    // TODO: отправить email на бэкенд при готовности эндпоинта.
    setStatus("success");
  }

  const onAccent = variant === "onAccent";

  if (status === "success") {
    return (
      <div
        className={`inline-flex items-center gap-2 rounded-pill px-5 py-3 text-sm ${
          onAccent ? "bg-paper text-ink" : "bg-ink text-paper"
        } ${className}`}
      >
        <Check className="h-4 w-4" />
        Спасибо. Мы свяжемся с вами по адресу {email.trim()}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className={`w-full max-w-md ${className}`} noValidate>
      <div
        className={`flex items-center gap-2 rounded-pill p-1.5 shadow-soft ${
          onAccent ? "bg-paper" : "border border-line bg-paper"
        }`}
      >
        <input
          type="email"
          inputMode="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (status === "error") setStatus("idle");
          }}
          placeholder="Рабочий email"
          aria-label="Рабочий email"
          className="min-w-0 flex-1 bg-transparent px-4 py-2.5 text-sm text-ink placeholder:text-muted focus:outline-none"
        />
        <button
          type="submit"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-pill bg-ink px-5 py-2.5 text-sm font-medium text-paper transition-transform duration-200 ease-out2 hover:scale-[1.02]"
        >
          {buttonLabel}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
      {status === "error" && (
        <p className={`mt-2 pl-4 text-xs ${onAccent ? "text-paper/90" : "text-accent-dark"}`}>
          Введите корректный рабочий email
        </p>
      )}
    </form>
  );
}

export default EmailCapture;
