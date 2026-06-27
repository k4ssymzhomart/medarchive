// Форматтеры для интерфейса MedPartners.
// Без дефисов в видимых строках, неразрывные пробелы в числах.

const NBSP = " ";

// Форматирует сумму в тенге: "16 600 ₸" с неразрывными пробелами между разрядами.
export function formatTenge(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const rounded = Math.round(n);
  const sign = rounded < 0 ? "−" : "";
  const digits = Math.abs(rounded).toString();
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  return `${sign}${grouped}${NBSP}₸`;
}

// Форматирует ISO дату в "ДД.ММ.ГГГГ". Пустую дату отдаёт как прочерк.
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    // Уже отформатированная или нестандартная строка: вернём как есть.
    return value;
  }
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

// Русские подписи для методов сопоставления.
export function matchMethodLabel(method: string | null | undefined): string {
  if (!method) return "Без метода";
  const map: Record<string, string> = {
    exact: "Точное совпадение",
    exact_code: "По коду",
    icd: "По коду МКБ",
    synonym: "По синониму",
    rapidfuzz: "Нечёткое совпадение",
    fuzzy: "Нечёткое совпадение",
    embedding: "По эмбеддингам",
    embeddings: "По эмбеддингам",
    rerank: "Реранкер",
    reranker: "Реранкер",
    llm: "Арбитр LLM",
    manual: "Вручную",
    human: "Вручную",
    confirmed: "Подтверждено",
    rejected: "Отклонено",
    corrected: "Исправлено вручную",
    none: "Без метода",
    unmatched: "Не сопоставлено",
  };
  return map[method] ?? method;
}

// Русские подписи для статусов обработки документов.
export function statusLabel(status: string | null | undefined): string {
  if (!status) return "Неизвестно";
  const map: Record<string, string> = {
    pending: "В очереди",
    processing: "Обработка",
    done: "Готово",
    error: "Ошибка",
    needs_review: "Нужна проверка",
  };
  return map[status] ?? status;
}
