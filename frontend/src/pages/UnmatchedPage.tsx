// Очередь несопоставленных позиций MedPartners.
// Переключатель режимов, карточки позиций с ценами и кандидатами в один клик.
// Острые углы, монохром плюс один акцент, иконки строго lucide-react.

import { useCallback, useEffect, useState } from "react";
import {
  Unlink,
  Check,
  X,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Building2,
  FileText,
  AlertTriangle,
  ClipboardCheck,
} from "lucide-react";
import {
  listUnmatched,
  postMatch,
  type UnmatchedItem,
  type UnmatchedMode,
  type MatchCandidate,
  type Page,
} from "../lib/api";
import { formatTenge, matchMethodLabel } from "../lib/format";
import {
  Button,
  Card,
  Badge,
  Spinner,
  EmptyState,
  ConfidenceBar,
} from "../components/ui";

const PAGE_SIZE = 20;

interface ModeTab {
  mode: UnmatchedMode;
  label: string;
}

const MODE_TABS: ModeTab[] = [
  { mode: "all", label: "Все" },
  { mode: "unmatched", label: "Несопоставленные" },
  { mode: "needs_review", label: "На ревью" },
  { mode: "anomaly", label: "Аномалии" },
];

// Состояние обработки конкретной позиции, чтобы блокировать кнопки точечно.
type RowState = "idle" | "saving" | "done";

export default function UnmatchedPage() {
  const [mode, setMode] = useState<UnmatchedMode>("unmatched");
  const [items, setItems] = useState<UnmatchedItem[]>([]);
  const [page, setPage] = useState<Page | null>(null);
  const [offset, setOffset] = useState(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Локальные статусы по item_id: сохранение и финальный результат.
  const [rowState, setRowState] = useState<Record<string, RowState>>({});
  const [rowResult, setRowResult] = useState<Record<string, string>>({});
  const [rowError, setRowError] = useState<Record<string, string>>({});

  const load = useCallback(
    async (nextMode: UnmatchedMode, nextOffset: number) => {
      setLoading(true);
      setError(null);
      try {
        const data = await listUnmatched({
          mode: nextMode,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setItems(data.items);
        setPage(data.page);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось загрузить очередь");
        setItems([]);
        setPage(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    load(mode, offset);
  }, [mode, offset, load]);

  function changeMode(next: UnmatchedMode) {
    if (next === mode) return;
    setMode(next);
    setOffset(0);
    setRowState({});
    setRowResult({});
    setRowError({});
  }

  async function runMatch(
    item: UnmatchedItem,
    serviceId: string | null,
    action: "confirm" | "reject",
    successText: string,
  ) {
    setRowState((s) => ({ ...s, [item.item_id]: "saving" }));
    setRowError((s) => {
      const next = { ...s };
      delete next[item.item_id];
      return next;
    });
    try {
      const res = await postMatch({
        item_id: item.item_id,
        service_id: serviceId,
        action,
      });
      const learned =
        res.synonyms_learned > 0
          ? ` Синонимов добавлено: ${res.synonyms_learned}.`
          : "";
      setRowState((s) => ({ ...s, [item.item_id]: "done" }));
      setRowResult((s) => ({ ...s, [item.item_id]: successText + learned }));
    } catch (e) {
      setRowState((s) => ({ ...s, [item.item_id]: "idle" }));
      setRowError((s) => ({
        ...s,
        [item.item_id]:
          e instanceof Error ? e.message : "Не удалось сохранить решение",
      }));
    }
  }

  function confirmCandidate(item: UnmatchedItem, candidate: MatchCandidate) {
    runMatch(
      item,
      candidate.service_id,
      "confirm",
      `Сопоставлено с услугой «${candidate.service_name}».`,
    );
  }

  function rejectItem(item: UnmatchedItem) {
    runMatch(item, null, "reject", "Позиция отклонена.");
  }

  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            Несопоставленные позиции
          </h1>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => load(mode, offset)}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4" />
            Обновить
          </Button>
        </div>
        <p className="text-sm text-neutral-500">
          Подтвердите подходящего кандидата в один клик или отклоните позицию.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {MODE_TABS.map((tab) => {
          const active = tab.mode === mode;
          return (
            <button
              key={tab.mode}
              type="button"
              onClick={() => changeMode(tab.mode)}
              className={[
                "rounded-sm border px-3 py-1.5 text-sm transition-colors",
                active
                  ? "border-accent/30 bg-accent/5 font-medium text-accent"
                  : "border-line bg-white text-neutral-700 hover:bg-neutral-50",
              ].join(" ")}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {loading && (
        <div className="py-20">
          <Spinner label="Загрузка очереди" className="justify-center" />
        </div>
      )}

      {!loading && error && (
        <Card className="border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <div className="mb-2 flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4" />
            Ошибка загрузки
          </div>
          <p className="mb-3">{error}</p>
          <Button variant="danger" size="sm" onClick={() => load(mode, offset)}>
            Повторить
          </Button>
        </Card>
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon={<ClipboardCheck className="h-8 w-8" />}
          title="Очередь пуста"
          description="В выбранном режиме нет позиций, требующих внимания."
        />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <UnmatchedCard
              key={item.item_id}
              item={item}
              state={rowState[item.item_id] ?? "idle"}
              result={rowResult[item.item_id]}
              rowError={rowError[item.item_id]}
              onConfirm={confirmCandidate}
              onReject={rejectItem}
            />
          ))}
        </div>
      )}

      {!loading && !error && total > 0 && (
        <div className="flex items-center justify-between gap-4 pt-1">
          <span className="num text-sm tabular-nums text-neutral-500">
            {from} – {to} из {total}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={!hasPrev}
            >
              <ChevronLeft className="h-4 w-4" />
              Назад
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={!hasNext}
            >
              Вперёд
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

interface UnmatchedCardProps {
  item: UnmatchedItem;
  state: RowState;
  result?: string;
  rowError?: string;
  onConfirm: (item: UnmatchedItem, candidate: MatchCandidate) => void;
  onReject: (item: UnmatchedItem) => void;
}

function UnmatchedCard({
  item,
  state,
  result,
  rowError,
  onConfirm,
  onReject,
}: UnmatchedCardProps) {
  const saving = state === "saving";
  const done = state === "done";

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-start gap-2">
            <Unlink className="mt-0.5 h-4 w-4 shrink-0 text-neutral-400" />
            <h2 className="text-base font-semibold text-ink">
              {item.service_name_raw || "Без названия"}
            </h2>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-neutral-500">
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" />
              {item.partner_name}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              {item.document_name}
            </span>
            {item.category && (
              <Badge tone="neutral">{item.category}</Badge>
            )}
            {item.is_anomaly && (
              <Badge tone="danger">
                <AlertTriangle className="h-3 w-3" />
                Аномалия
              </Badge>
            )}
            {item.needs_review && !item.is_anomaly && (
              <Badge tone="warning">На ревью</Badge>
            )}
          </div>
        </div>

        <div className="shrink-0 text-left sm:text-right">
          <div className="num text-lg font-semibold tabular-nums text-ink">
            {formatTenge(item.price_resident_kzt)}
          </div>
          <div className="num text-xs tabular-nums text-neutral-500">
            нерезидент {formatTenge(item.price_nonresident_kzt)}
          </div>
          {item.raw_price_label && (
            <div className="mt-1 text-xs text-neutral-400">
              {item.raw_price_label}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 border-t border-line pt-4">
        {done ? (
          <div className="flex items-center gap-2 text-sm text-emerald-700">
            <Check className="h-4 w-4" />
            <span>{result}</span>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="text-xs uppercase tracking-wide text-neutral-500">
              Кандидаты
            </div>

            {item.candidates.length === 0 ? (
              <p className="text-sm text-neutral-500">
                Подходящих кандидатов не найдено.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {item.candidates.map((candidate) => (
                  <li
                    key={`${candidate.service_id}-${candidate.rank}`}
                    className="flex flex-col gap-2 rounded-sm border border-line px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-ink">
                        {candidate.service_name}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <ConfidenceBar value={candidate.score} />
                        <span className="text-xs text-neutral-500">
                          {matchMethodLabel(candidate.method)}
                        </span>
                      </div>
                    </div>
                    <Button
                      variant="primary"
                      size="sm"
                      loading={saving}
                      disabled={saving}
                      onClick={() => onConfirm(item, candidate)}
                      className="shrink-0"
                    >
                      <Check className="h-4 w-4" />
                      Подтвердить
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex items-center justify-between gap-3 pt-1">
              {rowError ? (
                <span className="text-xs text-red-600">{rowError}</span>
              ) : (
                <span />
              )}
              <Button
                variant="danger"
                size="sm"
                loading={saving}
                disabled={saving}
                onClick={() => onReject(item)}
                className="shrink-0"
              >
                <X className="h-4 w-4" />
                Отклонить
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
