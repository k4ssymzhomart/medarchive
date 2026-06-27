// Очередь верификации MedPartners. Главный экран сопоставления.
// Три колонки: слева контекст источника, по центру извлечённые данные,
// справа предложенное сопоставление с кандидатами и действиями.
// Острые углы, монохром плюс акцент, иконки строго lucide-react.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  MapPin,
  Tag,
  AlertTriangle,
  Hash,
  Calendar,
  Banknote,
  Building2,
  Check,
  X,
  Pencil,
  Search as SearchIcon,
  ChevronLeft,
  ChevronRight,
  ListChecks,
  RefreshCw,
  CircleCheck,
} from "lucide-react";
import {
  listUnmatched,
  postMatch,
  search as searchApi,
  type UnmatchedItem,
  type MatchCandidate,
  type SearchResult,
} from "../lib/api";
import {
  formatTenge,
  formatDate,
  matchMethodLabel,
} from "../lib/format";
import {
  Button,
  Card,
  Badge,
  Spinner,
  EmptyState,
  ConfidenceBar,
} from "../components/ui";

const PAGE_SIZE = 20;

// Подпись строки контекста: иконка плюс метка и значение.
function ContextRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span className="mt-0.5 shrink-0 text-neutral-400">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="text-xs uppercase tracking-wide text-neutral-500">
          {label}
        </div>
        <div className="mt-0.5 break-words text-sm text-ink">{value}</div>
      </div>
    </div>
  );
}

// Блок цены: подпись, резидент, нерезидент.
function PriceBlock({
  label,
  resident,
  nonresident,
}: {
  label: string;
  resident: number | null;
  nonresident: number | null;
}) {
  return (
    <div className="rounded-sm border border-line bg-neutral-50 p-4">
      <div className="text-xs uppercase tracking-wide text-neutral-500">
        {label}
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-4">
        <span className="text-xs text-neutral-500">Резидент</span>
        <span className="num text-lg font-semibold tabular-nums text-ink">
          {formatTenge(resident)}
        </span>
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-4">
        <span className="text-xs text-neutral-500">Нерезидент</span>
        <span className="num text-lg font-semibold tabular-nums text-ink">
          {formatTenge(nonresident)}
        </span>
      </div>
    </div>
  );
}

export default function VerificationPage() {
  const [items, setItems] = useState<UnmatchedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [cursor, setCursor] = useState(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Состояние действия по текущему элементу.
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  // Выбранный кандидат (по умолчанию верхний). Ключ service_id.
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(
    null,
  );

  // Режим исправления: поиск услуги вручную.
  const [correctMode, setCorrectMode] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const searchTimer = useRef<number | null>(null);

  // Refs для стабильного доступа из обработчика клавиш без пере-подписки.
  const stateRef = useRef({
    loading, submitting, correctMode, cursor, offset,
    items, selectedServiceId, total,
  });
  useEffect(() => {
    stateRef.current = {
      loading, submitting, correctMode, cursor, offset,
      items, selectedServiceId, total,
    };
  });

  // Стабильные рефы для действий — инициализируются здесь, обновляются ниже.
  const onConfirmRef = useRef<() => void>(() => {});
  const onRejectRef = useRef<() => void>(() => {});

  const loadPage = useCallback(
    async (nextOffset: number, keepCursor = false) => {
      setLoading(true);
      setError(null);
      try {
        const res = await listUnmatched({
          mode: "needs_review",
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setItems(res.items);
        setTotal(res.page.total);
        setOffset(res.page.offset);
        if (!keepCursor) setCursor(0);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось загрузить очередь");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadPage(0);
  }, [loadPage]);

  const current: UnmatchedItem | undefined = items[cursor];

  // Сброс локального состояния при смене текущего элемента.
  useEffect(() => {
    setActionError(null);
    setCorrectMode(false);
    setSearchTerm("");
    setSearchResults([]);
    setSelectedServiceId(current?.candidates?.[0]?.service_id ?? null);
  }, [current?.item_id]);

  // Горячие клавиши: навигация и действия без мыши.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      const inInput = tag === "INPUT" || tag === "TEXTAREA";

      // Escape всегда закрывает режим исправления, даже из поля ввода.
      if (e.key === "Escape" && stateRef.current.correctMode) {
        e.preventDefault();
        setCorrectMode(false);
        setSearchTerm("");
        setSearchResults([]);
        return;
      }

      if (inInput || stateRef.current.loading || stateRef.current.submitting) return;
      if (stateRef.current.correctMode) return;

      const { cursor: cur, offset: off, items: its, selectedServiceId: sid } = stateRef.current;

      switch (e.key) {
        case "ArrowRight":
        case "j":
          e.preventDefault();
          if (cur + 1 < its.length) setCursor((c) => c + 1);
          break;
        case "ArrowLeft":
        case "k":
          e.preventDefault();
          if (cur > 0) setCursor((c) => c - 1);
          else if (off > 0) void loadPage(Math.max(0, off - PAGE_SIZE));
          break;
        case "Enter":
        case "y":
          if (sid) { e.preventDefault(); onConfirmRef.current(); }
          break;
        case "x":
          e.preventDefault();
          onRejectRef.current();
          break;
        case "e":
          e.preventDefault();
          setCorrectMode(true);
          break;
        case "1": case "2": case "3": case "4": case "5": {
          const idx = parseInt(e.key) - 1;
          const cand = its[cur]?.candidates?.[idx];
          if (cand) { e.preventDefault(); setSelectedServiceId(cand.service_id); }
          break;
        }
        default: break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [loadPage]);

  // Поиск услуг для режима исправления (с задержкой).
  useEffect(() => {
    if (!correctMode) return;
    const term = searchTerm.trim();
    if (searchTimer.current) window.clearTimeout(searchTimer.current);
    if (term.length < 2) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    searchTimer.current = window.setTimeout(async () => {
      try {
        const res = await searchApi({ q: term, limit: 12 });
        setSearchResults(res.results.filter((r) => r.kind === "service"));
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 280);
    return () => {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
    };
  }, [searchTerm, correctMode]);

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + items.length, total);
  const reviewedOnPage = cursor;

  const runAction = useCallback(
    async (
      action: "confirm" | "reject" | "correct",
      serviceId: string | null,
      note?: string,
    ) => {
      if (!current) return;
      setSubmitting(true);
      setActionError(null);
      try {
        const res = await postMatch({
          item_id: current.item_id,
          service_id: serviceId,
          action,
          note,
        });
        const verb =
          action === "confirm"
            ? "Подтверждено"
            : action === "reject"
              ? "Отклонено"
              : "Исправлено";
        const learned =
          res.synonyms_learned > 0
            ? `, синонимов добавлено ${res.synonyms_learned}`
            : "";
        setLastResult(`${verb}: ${current.service_name_raw}${learned}`);
        // Уберём обработанный элемент из текущей выборки локально,
        // чтобы очередь визуально сокращалась без полной перезагрузки.
        setTotal((t) => Math.max(0, t - 1));
        setItems((prev) => {
          const next = prev.filter((it) => it.item_id !== current.item_id);
          // Удержим курсор в границах.
          setCursor((c) => Math.min(c, Math.max(0, next.length - 1)));
          if (next.length === 0) {
            // Подтянем следующую страницу или перезагрузим текущую.
            const nextOffset =
              offset + PAGE_SIZE < total ? offset + PAGE_SIZE : 0;
            void loadPage(nextOffset);
          }
          return next;
        });
      } catch (e) {
        setActionError(
          e instanceof Error ? e.message : "Не удалось выполнить действие",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [current, offset, total, loadPage],
  );

  const onConfirm = useCallback(() => {
    if (!selectedServiceId) return;
    void runAction("confirm", selectedServiceId);
  }, [runAction, selectedServiceId]);

  const onReject = useCallback(() => {
    void runAction("reject", null);
  }, [runAction]);

  // Синхронизируем рефы с текущими коллбэками после каждого ре-рендера.
  useEffect(() => { onConfirmRef.current = onConfirm; }, [onConfirm]);
  useEffect(() => { onRejectRef.current = onReject; }, [onReject]);

  const onCorrect = useCallback(
    (serviceId: string, serviceName: string) => {
      void runAction("correct", serviceId, `Исправлено на: ${serviceName}`);
    },
    [runAction],
  );

  // --- Рендер состояний ---

  if (loading && items.length === 0) {
    return (
      <div className="space-y-6">
        <Header total={total} onRefresh={() => void loadPage(0)} loading />
        <div className="py-24">
          <Spinner label="Загрузка очереди" className="justify-center" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Header total={total} onRefresh={() => void loadPage(0)} />
        <EmptyState
          icon={<AlertTriangle className="h-8 w-8" />}
          title="Ошибка загрузки"
          description={error}
          action={
            <Button variant="primary" onClick={() => void loadPage(0)}>
              <RefreshCw className="h-4 w-4" />
              Повторить
            </Button>
          }
        />
      </div>
    );
  }

  if (!current) {
    return (
      <div className="space-y-6">
        <Header total={total} onRefresh={() => void loadPage(0)} />
        <EmptyState
          icon={<CircleCheck className="h-8 w-8 text-accent" />}
          title="Очередь пуста"
          description="Все позиции, требующие проверки, обработаны. Новые появятся после загрузки документов."
          action={
            <Button onClick={() => void loadPage(0)}>
              <RefreshCw className="h-4 w-4" />
              Обновить
            </Button>
          }
        />
      </div>
    );
  }

  const confidence = current.match_confidence;
  const topCandidate = current.candidates?.[0];

  return (
    <div className="space-y-6">
      <Header total={total} onRefresh={() => void loadPage(offset, true)} />

      {lastResult && (
        <div className="flex items-center gap-2 rounded-sm border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
          <CircleCheck className="h-4 w-4 shrink-0" />
          <span className="truncate">{lastResult}</span>
        </div>
      )}

      {/* Прогресс по очереди */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm text-neutral-600">
          <Badge tone="accent">
            <ListChecks className="h-3.5 w-3.5" />
            Позиция {pageStart + reviewedOnPage} из {total}
          </Badge>
          <span className="num tabular-nums text-neutral-500">
            Показаны {pageStart} по {pageEnd}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled={loading || (offset === 0 && cursor === 0)}
            onClick={() => {
              if (cursor > 0) setCursor((c) => c - 1);
              else if (offset > 0) void loadPage(Math.max(0, offset - PAGE_SIZE));
            }}
          >
            <ChevronLeft className="h-4 w-4" />
            Назад
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={loading || cursor + 1 >= items.length}
            onClick={() => setCursor((c) => Math.min(items.length - 1, c + 1))}
          >
            Дальше
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Три колонки */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* ЛЕВО: контекст источника */}
        <Card className="overflow-hidden">
          <div className="flex items-center gap-2 border-b border-line bg-neutral-50 px-4 py-3">
            <FileText className="h-4 w-4 text-neutral-500" />
            <span className="text-sm font-semibold">Источник</span>
          </div>
          <div className="divide-y divide-line">
            <ContextRow
              icon={<Building2 className="h-4 w-4" />}
              label="Партнёр"
              value={current.partner_name || "—"}
            />
            <ContextRow
              icon={<FileText className="h-4 w-4" />}
              label="Документ"
              value={current.document_name || "—"}
            />
            <ContextRow
              icon={<MapPin className="h-4 w-4" />}
              label="Страница и строка"
              value={
                <span className="num tabular-nums">
                  стр. {current.source_page ?? "—"}, строка{" "}
                  {current.source_row ?? "—"}
                </span>
              }
            />
            <ContextRow
              icon={<Banknote className="h-4 w-4" />}
              label="Исходная подпись цены"
              value={current.raw_price_label || "—"}
            />
            <ContextRow
              icon={<Tag className="h-4 w-4" />}
              label="Категория"
              value={current.category || "—"}
            />
          </div>
        </Card>

        {/* ЦЕНТР: извлечённые данные */}
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-2 border-b border-line bg-neutral-50 px-4 py-3">
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4 text-neutral-500" />
              <span className="text-sm font-semibold">Извлечённые данные</span>
            </div>
            {current.is_anomaly && (
              <Badge tone="danger">
                <AlertTriangle className="h-3.5 w-3.5" />
                Аномалия
              </Badge>
            )}
          </div>
          <div className="space-y-4 p-4">
            <div>
              <div className="text-xs uppercase tracking-wide text-neutral-500">
                Наименование услуги
              </div>
              <div className="mt-1 text-base font-medium leading-snug text-ink">
                {current.service_name_raw || "—"}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {current.service_code_source && (
                <Badge tone="neutral">
                  <Hash className="h-3.5 w-3.5" />
                  Код {current.service_code_source}
                </Badge>
              )}
              <Badge tone="neutral">
                <Calendar className="h-3.5 w-3.5" />
                {formatDate(current.effective_date)}
              </Badge>
              {current.needs_review && (
                <Badge tone="warning">Нужна проверка</Badge>
              )}
            </div>

            <PriceBlock
              label="Цена"
              resident={current.price_resident_kzt}
              nonresident={current.price_nonresident_kzt}
            />

            {current.price_original !== null && (
              <div className="num flex items-baseline justify-between gap-4 text-xs text-neutral-500 tabular-nums">
                <span>Оригинал</span>
                <span>
                  {current.price_original} {current.currency_original}
                </span>
              </div>
            )}
          </div>
        </Card>

        {/* ПРАВО: предложенное сопоставление */}
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-2 border-b border-line bg-neutral-50 px-4 py-3">
            <div className="flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-neutral-500" />
              <span className="text-sm font-semibold">Сопоставление</span>
            </div>
            <Badge tone={confidenceTone(confidence)}>
              {matchMethodLabel(current.match_method)}
            </Badge>
          </div>

          <div className="space-y-4 p-4">
            <div>
              <div className="text-xs uppercase tracking-wide text-neutral-500">
                Уверенность сопоставления
              </div>
              <div className="mt-2">
                <ConfidenceBar value={confidence} />
              </div>
            </div>

            {!correctMode && (
              <CandidateList
                candidates={current.candidates ?? []}
                selectedServiceId={selectedServiceId}
                onSelect={setSelectedServiceId}
              />
            )}

            {correctMode && (
              <CorrectPanel
                searchTerm={searchTerm}
                onSearchTerm={setSearchTerm}
                results={searchResults}
                loading={searchLoading}
                submitting={submitting}
                onPick={onCorrect}
                onCancel={() => {
                  setCorrectMode(false);
                  setSearchTerm("");
                  setSearchResults([]);
                }}
              />
            )}

            {actionError && (
              <div className="flex items-start gap-2 rounded-sm border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            {!correctMode && (
              <div className="space-y-2 border-t border-line pt-4">
                <Button
                  variant="primary"
                  className="w-full"
                  loading={submitting}
                  disabled={submitting || !selectedServiceId}
                  onClick={onConfirm}
                >
                  <Check className="h-4 w-4" />
                  Подтвердить
                  {topCandidate &&
                  selectedServiceId === topCandidate.service_id
                    ? " верхний"
                    : " выбранный"}
                </Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="secondary"
                    disabled={submitting}
                    onClick={() => setCorrectMode(true)}
                  >
                    <Pencil className="h-4 w-4" />
                    Исправить
                  </Button>
                  <Button
                    variant="danger"
                    disabled={submitting}
                    onClick={onReject}
                  >
                    <X className="h-4 w-4" />
                    Отклонить
                  </Button>
                </div>
                <KbdHints />
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

// --- Заголовок страницы ---

function Header({
  total,
  onRefresh,
  loading,
}: {
  total: number;
  onRefresh: () => void;
  loading?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Очередь верификации
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Проверка автоматических сопоставлений. Подтвердите, исправьте или
          отклоните каждую позицию.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Badge tone="warning">
          <ListChecks className="h-3.5 w-3.5" />В очереди {total}
        </Badge>
        <Button size="sm" variant="secondary" onClick={onRefresh} loading={loading}>
          <RefreshCw className="h-4 w-4" />
          Обновить
        </Button>
      </div>
    </div>
  );
}

// --- Список кандидатов ---

function CandidateList({
  candidates,
  selectedServiceId,
  onSelect,
}: {
  candidates: MatchCandidate[];
  selectedServiceId: string | null;
  onSelect: (id: string) => void;
}) {
  if (candidates.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-line bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
        Кандидаты не найдены. Используйте действие Исправить, чтобы выбрать
        услугу вручную.
      </div>
    );
  }
  return (
    <div>
      <div className="mb-2 text-xs uppercase tracking-wide text-neutral-500">
        Кандидаты
      </div>
      <ul className="space-y-2">
        {candidates.map((c) => {
          const active = c.service_id === selectedServiceId;
          return (
            <li key={`${c.service_id}-${c.rank}`}>
              <button
                type="button"
                onClick={() => onSelect(c.service_id)}
                className={[
                  "w-full rounded-sm border px-3 py-2.5 text-left transition-colors",
                  active
                    ? "border-accent bg-accent/5"
                    : "border-line bg-white hover:bg-neutral-50",
                ].join(" ")}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {c.service_name}
                  </span>
                  {active && (
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  )}
                </div>
                <div className="mt-2 flex items-center justify-between gap-3">
                  <ConfidenceBar value={c.score} />
                  <span className="shrink-0 text-xs text-neutral-500">
                    {matchMethodLabel(c.method)}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// --- Панель исправления (поиск услуги вручную) ---

function CorrectPanel({
  searchTerm,
  onSearchTerm,
  results,
  loading,
  submitting,
  onPick,
  onCancel,
}: {
  searchTerm: string;
  onSearchTerm: (v: string) => void;
  results: SearchResult[];
  loading: boolean;
  submitting: boolean;
  onPick: (serviceId: string, serviceName: string) => void;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs uppercase tracking-wide text-neutral-500">
          Выбор услуги вручную
        </div>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={submitting}>
          <ChevronLeft className="h-4 w-4" />
          Назад
        </Button>
      </div>

      <div className="flex items-center gap-2 rounded-sm border border-line bg-white px-3">
        <SearchIcon className="h-4 w-4 shrink-0 text-neutral-400" />
        <input
          autoFocus
          value={searchTerm}
          onChange={(e) => onSearchTerm(e.target.value)}
          placeholder="Название услуги или код"
          className="h-10 w-full border-0 bg-transparent text-sm text-ink outline-none placeholder:text-neutral-400"
        />
      </div>

      {loading && <Spinner label="Поиск услуг" />}

      {!loading && searchTerm.trim().length >= 2 && results.length === 0 && (
        <div className="rounded-sm border border-dashed border-line bg-neutral-50 px-4 py-6 text-center text-sm text-neutral-500">
          Ничего не найдено по запросу.
        </div>
      )}

      {!loading && results.length > 0 && (
        <ul className="max-h-72 space-y-2 overflow-y-auto">
          {results.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                disabled={submitting}
                onClick={() => onPick(r.id, r.title)}
                className="w-full rounded-sm border border-line bg-white px-3 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent/5 disabled:opacity-50"
              >
                <div className="text-sm font-medium text-ink">{r.title}</div>
                {r.subtitle && (
                  <div className="mt-0.5 text-xs text-neutral-500">
                    {r.subtitle}
                  </div>
                )}
                {r.category && (
                  <div className="mt-1">
                    <Badge tone="neutral">{r.category}</Badge>
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Клавишная подсказка: маленький ярлык для клавиши.
function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded-[2px] border border-neutral-300 bg-neutral-100 px-1 font-mono text-[10px] leading-none text-neutral-500">
      {children}
    </kbd>
  );
}

// Панель горячих клавиш под кнопками действий.
function KbdHints() {
  return (
    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 border-t border-dashed border-line pt-3">
      {(
        [
          [["Enter", "y"], "подтвердить"],
          [["x"], "отклонить"],
          [["e"], "исправить"],
          [["←", "→"], "навигация"],
          [["1–3"], "кандидат"],
          [["Esc"], "отмена"],
        ] as [string[], string][]
      ).map(([keys, label]) => (
        <span key={label} className="flex items-center gap-1 text-xs text-neutral-400">
          {keys.map((k) => <Kbd key={k}>{k}</Kbd>)}
          <span>{label}</span>
        </span>
      ))}
    </div>
  );
}

// Тон бейджа по уровню уверенности.
function confidenceTone(
  value: number | null | undefined,
): "success" | "warning" | "danger" | "neutral" {
  if (value === null || value === undefined) return "neutral";
  if (value >= 0.85) return "success";
  if (value >= 0.6) return "warning";
  return "danger";
}
