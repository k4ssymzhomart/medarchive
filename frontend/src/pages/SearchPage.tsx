// Страница поиска MedServicePrice.
// Единое поле поиска вызывает search(q), результаты группируются по виду:
// услуги раскрываются в список партнёров с ценами, партнёры ведут на карточку.
// Острые углы, монохром плюс один акцент, иконки строго lucide-react.

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  Building2,
  Stethoscope,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ChevronLeft,
  X,
} from "lucide-react";
import {
  search,
  getServicePartners,
  type SearchResult,
  type ServicePartner,
} from "../lib/api";
import { formatTenge, formatDate } from "../lib/format";
import {
  Card,
  Badge,
  Button,
  Spinner,
  EmptyState,
  Table,
  THead,
  TBody,
  TR,
  TH,
  TD,
} from "../components/ui";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 320;

export default function SearchPage() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);

  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [tookMs, setTookMs] = useState<number | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Раскрытая услуга и её партнёры (по service_id).
  const [openServiceId, setOpenServiceId] = useState<string | null>(null);

  // Сбрасываем смещение, когда меняется текст запроса.
  const debounceRef = useRef<number | null>(null);
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      const next = input.trim();
      setQuery(next);
      setOffset(0);
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [input]);

  // Загрузка результатов поиска.
  useEffect(() => {
    if (!query) {
      setResults([]);
      setTotal(0);
      setTookMs(null);
      setError(null);
      setLoading(false);
      setOpenServiceId(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    search({ q: query, limit: PAGE_SIZE, offset })
      .then((res) => {
        if (cancelled) return;
        setResults(res.results);
        setTotal(res.total);
        setTookMs(res.took_ms);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setResults([]);
        setTotal(0);
        setError(err instanceof Error ? err.message : "Не удалось выполнить поиск");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [query, offset]);

  // Закрываем раскрытую услугу при смене страницы или запроса.
  useEffect(() => {
    setOpenServiceId(null);
  }, [query, offset]);

  const toggleService = useCallback((id: string) => {
    setOpenServiceId((prev) => (prev === id ? null : id));
  }, []);

  const services = results.filter((r) => r.kind === "service");
  const partners = results.filter((r) => r.kind === "partner");

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Поиск</h1>
        <p className="text-sm text-neutral-500">
          Услуги и партнёры по названию, синониму или городу
        </p>
      </header>

      {/* Поле поиска */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-neutral-400" />
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Найти услугу или партнёра"
          autoFocus
          className="h-12 w-full rounded-sm border border-line bg-white pl-11 pr-11 text-base text-ink outline-none placeholder:text-neutral-400 focus:border-accent"
        />
        {input && (
          <button
            type="button"
            onClick={() => setInput("")}
            aria-label="Очистить"
            className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-sm border border-transparent text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Подсказка по времени поиска */}
      {query && !loading && !error && (
        <div className="flex items-center justify-between text-xs text-neutral-400">
          <span>
            Найдено{" "}
            <span className="num font-medium text-neutral-600">{total}</span>
          </span>
          {tookMs !== null && (
            <span className="num">за {tookMs} мс</span>
          )}
        </div>
      )}

      {/* Состояния */}
      {!query && (
        <EmptyState
          icon={<Search className="h-8 w-8" />}
          title="Начните вводить запрос"
          description="Введите название услуги, синоним, код или имя партнёра, чтобы увидеть результаты."
        />
      )}

      {query && loading && (
        <div className="py-16">
          <Spinner label="Идёт поиск" className="justify-center" />
        </div>
      )}

      {query && !loading && error && (
        <Card className="border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-3 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="flex flex-col gap-2">
              <span className="font-medium">Ошибка поиска</span>
              <span className="text-red-600">{error}</span>
              <div>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => {
                    // Повтор: сбрасываем и заново задаём текущий запрос.
                    const q = query;
                    setQuery("");
                    window.setTimeout(() => setQuery(q), 0);
                  }}
                >
                  Повторить
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {query && !loading && !error && total === 0 && (
        <EmptyState
          icon={<Search className="h-8 w-8" />}
          title="Ничего не найдено"
          description="Попробуйте изменить запрос или проверить раскладку."
        />
      )}

      {query && !loading && !error && total > 0 && (
        <div className="flex flex-col gap-8">
          {/* Услуги */}
          {services.length > 0 && (
            <section className="flex flex-col gap-3">
              <SectionHeader
                icon={<Stethoscope className="h-4 w-4" />}
                title="Услуги"
                count={services.length}
              />
              <div className="flex flex-col gap-2">
                {services.map((r) => (
                  <ServiceRow
                    key={r.id}
                    result={r}
                    open={openServiceId === r.id}
                    onToggle={() => toggleService(r.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Партнёры */}
          {partners.length > 0 && (
            <section className="flex flex-col gap-3">
              <SectionHeader
                icon={<Building2 className="h-4 w-4" />}
                title="Партнёры"
                count={partners.length}
              />
              <div className="flex flex-col gap-2">
                {partners.map((r) => (
                  <PartnerRow key={r.id} result={r} />
                ))}
              </div>
            </section>
          )}

          {/* Пагинация */}
          {(hasPrev || hasNext) && (
            <div className="flex items-center justify-between border-t border-line pt-4">
              <span className="num text-xs text-neutral-500">
                {from} {"–"} {to} из {total}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!hasPrev}
                  onClick={() =>
                    setOffset((o) => Math.max(0, o - PAGE_SIZE))
                  }
                >
                  <ChevronLeft className="h-4 w-4" />
                  Назад
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!hasNext}
                  onClick={() => setOffset((o) => o + PAGE_SIZE)}
                >
                  Далее
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- Заголовок секции ---

function SectionHeader({
  icon,
  title,
  count,
}: {
  icon: ReactNode;
  title: string;
  count: number;
}) {
  return (
    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
      <span className="text-neutral-400">{icon}</span>
      <span>{title}</span>
      <span className="num text-neutral-400">{count}</span>
    </div>
  );
}

// --- Строка партнёра ---

function PartnerRow({ result }: { result: SearchResult }) {
  return (
    <Link to={`/app/partners/${result.id}`} className="block">
      <Card className="flex items-center justify-between gap-4 p-4 transition-colors hover:border-accent/40 hover:bg-neutral-50">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border border-line bg-white text-neutral-500">
            <Building2 className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="truncate font-medium text-ink">{result.title}</div>
            {result.subtitle && (
              <div className="truncate text-sm text-neutral-500">
                {result.subtitle}
              </div>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {result.category && <Badge tone="neutral">{result.category}</Badge>}
          <ChevronRight className="h-4 w-4 text-neutral-400" />
        </div>
      </Card>
    </Link>
  );
}

// --- Строка услуги с раскрытием партнёров ---

function ServiceRow({
  result,
  open,
  onToggle,
}: {
  result: SearchResult;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 p-4 text-left transition-colors hover:bg-neutral-50"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border border-line bg-white text-neutral-500">
            <Stethoscope className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="truncate font-medium text-ink">{result.title}</div>
            {result.subtitle && (
              <div className="truncate text-sm text-neutral-500">
                {result.subtitle}
              </div>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {result.category && <Badge tone="neutral">{result.category}</Badge>}
          {open ? (
            <ChevronDown className="h-4 w-4 text-accent" />
          ) : (
            <ChevronRight className="h-4 w-4 text-neutral-400" />
          )}
        </div>
      </button>

      {open && (
        <div className="border-t border-line bg-neutral-50/50 p-4">
          <ServicePartnersPanel serviceId={result.id} />
        </div>
      )}
    </Card>
  );
}

// --- Панель с партнёрами и ценами выбранной услуги ---

function ServicePartnersPanel({ serviceId }: { serviceId: string }) {
  const [items, setItems] = useState<ServicePartner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getServicePartners(serviceId)
      .then((data) => {
        if (cancelled) return;
        // Сортируем по цене для резидентов по возрастанию, пустые цены в конец.
        const sorted = [...data].sort((a, b) => {
          const pa = a.price_resident_kzt;
          const pb = b.price_resident_kzt;
          if (pa === null && pb === null) return 0;
          if (pa === null) return 1;
          if (pb === null) return -1;
          return pa - pb;
        });
        setItems(sorted);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Не удалось загрузить партнёров",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [serviceId]);

  if (loading) {
    return <Spinner label="Загрузка партнёров" />;
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 text-sm text-red-700">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-sm text-neutral-500">
        Нет партнёров с ценой на эту услугу.
      </div>
    );
  }

  return (
    <Table className="bg-white">
      <THead>
        <TR>
          <TH>Партнёр</TH>
          <TH>Город</TH>
          <TH className="text-right">Резидент</TH>
          <TH className="text-right">Нерезидент</TH>
          <TH className="text-right">Дата</TH>
        </TR>
      </THead>
      <TBody>
        {items.map((p) => (
          <TR key={p.item_id} className="hover:bg-neutral-50">
            <TD>
              <Link
                to={`/app/partners/${p.partner_id}`}
                className="font-medium text-ink underline-offset-2 hover:text-accent hover:underline"
              >
                {p.partner_name}
              </Link>
            </TD>
            <TD className="text-neutral-600">{p.city || "—"}</TD>
            <TD className="num text-right tabular-nums text-ink">
              {formatTenge(p.price_resident_kzt)}
            </TD>
            <TD className="num text-right tabular-nums text-neutral-600">
              {formatTenge(p.price_nonresident_kzt)}
            </TD>
            <TD className="num text-right text-neutral-500">
              {formatDate(p.effective_date)}
            </TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
