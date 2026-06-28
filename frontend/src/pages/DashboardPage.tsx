// Дашборд MedServicePrice: живой отчёт о качестве (раздел 16).
// Большие карточки метрик, hero число доли сопоставления, разрезы по форматам
// и партнёрам с тонкими столбчатыми шкалами из div. Острые углы, монохром плюс акцент.

import { useCallback, useEffect, useState } from "react";
import {
  RefreshCw,
  FileText,
  CheckCircle2,
  Target,
  Eye,
  Unlink,
  TriangleAlert,
  Timer,
  Stethoscope,
  Building2,
  AlertCircle,
} from "lucide-react";
import { getStats } from "../lib/api";
import type { Stats, PartnerStat } from "../lib/api";
import { statusLabel } from "../lib/format";
import {
  Button,
  Card,
  Badge,
  Stat,
  Spinner,
  EmptyState,
  Table,
  THead,
  TBody,
  TR,
  TH,
  TD,
} from "../components/ui";

// Доля сопоставления считается успешной от этого порога.
const MATCH_TARGET = 0.7;

// Неразрывный пробел для разрядов в числах.
const NBSP = " ";

// Целое число с неразрывными пробелами между разрядами.
function formatInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

// Доля от 0 до 1 в проценты с одним знаком, без лишнего хвоста.
function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const pct = value * 100;
  const rounded = Math.round(pct * 10) / 10;
  const text = Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1);
  return `${text}${NBSP}%`;
}

// Секунды в читаемую длительность без дефисов.
function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 60) {
    const rounded = Math.round(value * 10) / 10;
    const text = Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1);
    return `${text}${NBSP}с`;
  }
  const m = Math.floor(value / 60);
  const s = Math.round(value % 60);
  return `${m}${NBSP}мин ${s}${NBSP}с`;
}

// Тонкая столбчатая шкала из div. Острые углы, заливка акцентом.
function BarMeter({
  value,
  max,
  accent = false,
}: {
  value: number;
  max: number;
  accent?: boolean;
}) {
  const safeMax = max > 0 ? max : 1;
  const pct = Math.max(0, Math.min(100, Math.round((value / safeMax) * 100)));
  return (
    <div className="h-2 w-full overflow-hidden rounded-none border border-line bg-neutral-100">
      <div
        className={accent ? "h-full bg-accent" : "h-full bg-ink"}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (mode: "initial" | "refresh") => {
    if (mode === "initial") setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const data = await getStats();
      setStats(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить статистику");
    } finally {
      if (mode === "initial") setLoading(false);
      else setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load("initial");
  }, [load]);

  // Первичная загрузка.
  if (loading) {
    return (
      <div className="py-24">
        <Spinner label="Загрузка статистики" className="justify-center" />
      </div>
    );
  }

  // Ошибка без ранее загруженных данных.
  if (error && !stats) {
    return (
      <EmptyState
        title="Не удалось загрузить дашборд"
        description={error}
        icon={<AlertCircle className="h-8 w-8" />}
        action={
          <Button variant="primary" onClick={() => void load("initial")}>
            <RefreshCw className="h-4 w-4" />
            Повторить
          </Button>
        }
      />
    );
  }

  if (!stats) {
    return (
      <EmptyState
        title="Нет данных"
        description="Статистика пока недоступна. Загрузите прайс листы партнёров."
        icon={<FileText className="h-8 w-8" />}
      />
    );
  }

  const matchOk = stats.match_rate >= MATCH_TARGET;
  const formatRows = [...stats.by_format].sort((a, b) => b.items - a.items);
  const partnerRows = [...stats.by_partner].sort((a, b) => b.items - a.items);
  const maxPartnerItems = partnerRows.reduce(
    (m: number, r: PartnerStat) => Math.max(m, r.items),
    0,
  );

  // Порядок статусов документов для подписей.
  const statusOrder = [
    "done",
    "processing",
    "pending",
    "needs_review",
    "error",
  ];
  const statusEntries = Object.entries(stats.documents_by_status).sort(
    (a, b) => statusOrder.indexOf(a[0]) - statusOrder.indexOf(b[0]),
  );

  return (
    <div className="flex flex-col gap-8">
      {/* Шапка */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            Дашборд качества
          </h1>
          <p className="mt-1 text-sm text-neutral-500">
            Живой отчёт по обработке прайс листов и сопоставлению услуг.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => void load("refresh")}
          loading={refreshing}
          disabled={refreshing}
        >
          {!refreshing && <RefreshCw className="h-4 w-4" />}
          Обновить
        </Button>
      </header>

      {/* Сообщение об ошибке поверх ранее загруженных данных */}
      {error && (
        <Card className="flex items-center gap-2 border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </Card>
      )}

      {/* Hero: доля сопоставления */}
      <Card className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-neutral-500">
              <Target className="h-4 w-4" />
              Доля сопоставления услуг
            </div>
            <div
              className={
                "num mt-3 text-6xl font-semibold leading-none tabular-nums " +
                (matchOk ? "text-accent" : "text-ink")
              }
            >
              {formatPct(stats.match_rate)}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
              <Badge tone={matchOk ? "accent" : "warning"}>
                {matchOk ? "Цель достигнута" : "Ниже цели"}
              </Badge>
              <span>
                Цель {formatPct(MATCH_TARGET)}. Сопоставлено{" "}
                <span className="num tabular-nums text-ink">
                  {formatInt(stats.items_matched)}
                </span>{" "}
                из{" "}
                <span className="num tabular-nums text-ink">
                  {formatInt(stats.items_total)}
                </span>
              </span>
            </div>
          </div>

          {/* Широкая шкала прогресса к цели */}
          <div className="w-full max-w-md">
            <div className="mb-2 flex items-center justify-between text-xs text-neutral-500">
              <span>Прогресс</span>
              <span className="num tabular-nums">{formatPct(stats.match_rate)}</span>
            </div>
            <div className="relative h-3 w-full overflow-hidden rounded-none border border-line bg-neutral-100">
              <div
                className={matchOk ? "h-full bg-accent" : "h-full bg-ink"}
                style={{
                  width: `${Math.max(0, Math.min(100, Math.round(stats.match_rate * 100)))}%`,
                }}
              />
              {/* Отметка цели */}
              <div
                className="absolute top-0 h-full w-px bg-accent"
                style={{ left: `${Math.round(MATCH_TARGET * 100)}%` }}
                aria-hidden="true"
              />
            </div>
            <div className="mt-1 flex justify-between text-[11px] text-neutral-400">
              <span>0 %</span>
              <span>Цель {formatPct(MATCH_TARGET)}</span>
              <span>100 %</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Сетка ключевых метрик */}
      <section>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          <Stat
            label="Документы"
            value={
              <span className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-neutral-400" />
                {formatInt(stats.documents_total)}
              </span>
            }
            hint={
              statusEntries.length > 0 ? (
                <span className="num tabular-nums">
                  {statusEntries
                    .map(([s, c]) => `${statusLabel(s)} ${formatInt(c)}`)
                    .join(" · ")}
                </span>
              ) : (
                "Нет загруженных документов"
              )
            }
          />
          <Stat
            label="Активные позиции"
            value={
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-neutral-400" />
                {formatInt(stats.items_active)}
              </span>
            }
            hint={`Всего позиций ${formatInt(stats.items_total)}`}
          />
          <Stat
            label="Нужна проверка"
            value={
              <span className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-amber-500" />
                {formatInt(stats.needs_review_count)}
              </span>
            }
            hint="Низкая уверенность сопоставления"
          />
          <Stat
            label="Несопоставленные"
            value={
              <span className="flex items-center gap-2">
                <Unlink className="h-5 w-5 text-neutral-400" />
                {formatInt(stats.unmatched_count)}
              </span>
            }
            hint="Без привязки к справочнику"
          />
          <Stat
            label="Аномалии цен"
            value={
              <span className="flex items-center gap-2">
                <TriangleAlert className="h-5 w-5 text-red-500" />
                {formatInt(stats.anomaly_count)}
              </span>
            }
            hint="Подозрительные значения"
          />
          <Stat
            label="Среднее время"
            value={
              <span className="flex items-center gap-2">
                <Timer className="h-5 w-5 text-neutral-400" />
                {formatSeconds(stats.avg_processing_seconds)}
              </span>
            }
            hint="Обработка одного документа"
          />
          <Stat
            label="Услуги"
            value={
              <span className="flex items-center gap-2">
                <Stethoscope className="h-5 w-5 text-neutral-400" />
                {formatInt(stats.services_total)}
              </span>
            }
            hint="Записей в справочнике"
          />
          <Stat
            label="Партнёры"
            value={
              <span className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-neutral-400" />
                {formatInt(stats.partners_total)}
              </span>
            }
            hint="Активных и архивных"
          />
        </div>
      </section>

      {/* Разрез по форматам файлов */}
      <section className="flex flex-col gap-3">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              По формату файла
            </h2>
            <p className="mt-1 text-sm text-neutral-500">
              Сканы и фотографии обрабатываются наравне с таблицами.
            </p>
          </div>
        </div>
        {formatRows.length === 0 ? (
          <EmptyState
            title="Нет данных по форматам"
            description="Загрузите хотя бы один прайс лист, чтобы увидеть разрез."
            icon={<FileText className="h-8 w-8" />}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Формат</TH>
                <TH className="text-right">Документы</TH>
                <TH className="text-right">Позиции</TH>
                <TH className="text-right">Сопоставлено</TH>
                <TH className="w-56">Доля сопоставления</TH>
              </TR>
            </THead>
            <TBody>
              {formatRows.map((row) => {
                const ok = row.match_rate >= MATCH_TARGET;
                return (
                  <TR key={row.file_format}>
                    <TD className="font-medium uppercase">
                      {row.file_format || "—"}
                    </TD>
                    <TD className="num text-right tabular-nums">
                      {formatInt(row.documents)}
                    </TD>
                    <TD className="num text-right tabular-nums">
                      {formatInt(row.items)}
                    </TD>
                    <TD className="num text-right tabular-nums">
                      {formatInt(row.matched)}
                    </TD>
                    <TD>
                      <div className="flex items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <BarMeter
                            value={row.match_rate * 100}
                            max={100}
                            accent={ok}
                          />
                        </div>
                        <span className="num w-14 shrink-0 text-right text-xs tabular-nums text-neutral-600">
                          {formatPct(row.match_rate)}
                        </span>
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </section>

      {/* Разрез по партнёрам */}
      <section className="flex flex-col gap-3">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              По партнёрам
            </h2>
            <p className="mt-1 text-sm text-neutral-500">
              Объём позиций и качество сопоставления по каждому партнёру.
            </p>
          </div>
          {partnerRows.length > 0 && (
            <Badge tone="neutral">
              Всего {formatInt(partnerRows.length)}
            </Badge>
          )}
        </div>
        {partnerRows.length === 0 ? (
          <EmptyState
            title="Нет данных по партнёрам"
            description="Позиции появятся после загрузки прайс листов."
            icon={<Building2 className="h-8 w-8" />}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Партнёр</TH>
                <TH className="w-40">Объём позиций</TH>
                <TH className="text-right">Позиции</TH>
                <TH className="text-right">Сопоставлено</TH>
                <TH className="w-56">Доля сопоставления</TH>
              </TR>
            </THead>
            <TBody>
              {partnerRows.map((row) => {
                const ok = row.match_rate >= MATCH_TARGET;
                return (
                  <TR key={row.partner}>
                    <TD className="font-medium text-ink">{row.partner}</TD>
                    <TD>
                      <BarMeter value={row.items} max={maxPartnerItems} />
                    </TD>
                    <TD className="num text-right tabular-nums">
                      {formatInt(row.items)}
                    </TD>
                    <TD className="num text-right tabular-nums">
                      {formatInt(row.matched)}
                    </TD>
                    <TD>
                      <div className="flex items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <BarMeter
                            value={row.match_rate * 100}
                            max={100}
                            accent={ok}
                          />
                        </div>
                        <span className="num w-14 shrink-0 text-right text-xs tabular-nums text-neutral-600">
                          {formatPct(row.match_rate)}
                        </span>
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </section>
    </div>
  );
}
