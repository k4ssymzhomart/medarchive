// Страница партнёра MedPartners.
// Шапка партнёра, полный прайс лист с пагинацией и история цен по услуге.
// Острые углы, монохром плюс акцент, иконки строго lucide-react, тексты на русском.

import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Building2,
  MapPin,
  Mail,
  Phone,
  Hash,
  AlertTriangle,
  CheckCircle2,
  History,
  ChevronRight,
  ChevronLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  X,
  FileText,
} from "lucide-react";

import {
  listPartners,
  getPartnerServices,
  getPriceHistory,
} from "../lib/api";
import type { Partner, PriceItem, PriceHistory } from "../lib/api";
import { formatTenge, formatDate, matchMethodLabel } from "../lib/format";
import {
  Button,
  Card,
  Badge,
  Table,
  THead,
  TBody,
  TR,
  TH,
  TD,
  Spinner,
  EmptyState,
  ConfidenceBar,
} from "../components/ui";

const PAGE_SIZE = 25;

// Бейдж совпадения для строки прайса.
function MatchBadge({ item }: { item: PriceItem }) {
  if (!item.service_id) {
    return <Badge tone="neutral">Не сопоставлено</Badge>;
  }
  if (item.is_verified) {
    return (
      <Badge tone="success">
        <CheckCircle2 className="h-3 w-3" />
        Подтверждено
      </Badge>
    );
  }
  if (item.needs_review) {
    return <Badge tone="warning">Нужна проверка</Badge>;
  }
  return <Badge tone="accent">{matchMethodLabel(item.match_method)}</Badge>;
}

// Панель истории цен по выбранной услуге партнёра.
function HistoryPanel({
  partnerId,
  item,
  onClose,
}: {
  partnerId: string;
  item: PriceItem;
  onClose: () => void;
}) {
  const [data, setData] = useState<PriceHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!item.service_id) return;
    let alive = true;
    setLoading(true);
    setError(null);
    setData(null);
    getPriceHistory(partnerId, item.service_id)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : "Ошибка загрузки");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [partnerId, item.service_id]);

  const title = data?.service_name || item.service_name_raw;

  return (
    <Card className="p-0">
      <div className="flex items-start justify-between gap-4 border-b border-line px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <History className="h-4 w-4 shrink-0 text-accent" />
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wide text-neutral-500">
              История цен
            </div>
            <div className="truncate text-sm font-medium text-ink">{title}</div>
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Закрыть">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4">
        {loading && <Spinner label="Загрузка истории" />}

        {!loading && error && (
          <div className="flex items-center gap-2 rounded-sm border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && data && data.points.length === 0 && (
          <EmptyState
            title="Нет точек истории"
            description="Для этой услуги пока нет ни одной зафиксированной версии цены."
            icon={<History className="h-6 w-6" />}
          />
        )}

        {!loading && !error && data && data.points.length > 0 && (
          <Table>
            <THead>
              <TR>
                <TH>Дата</TH>
                <TH className="text-right">Резидент</TH>
                <TH className="text-right">Нерезидент</TH>
                <TH className="text-right">Изменение</TH>
                <TH>Документ</TH>
                <TH>Формат</TH>
              </TR>
            </THead>
            <TBody>
              {data.points.map((p) => {
                const pct = p.pct_change;
                const up = pct !== null && pct > 0;
                const down = pct !== null && pct < 0;
                return (
                  <TR key={p.item_id}>
                    <TD className="whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {formatDate(p.effective_date)}
                        {!p.is_active && (
                          <Badge tone="neutral">Архив</Badge>
                        )}
                      </div>
                    </TD>
                    <TD className="num whitespace-nowrap text-right tabular-nums">
                      {formatTenge(p.price_resident_kzt)}
                    </TD>
                    <TD className="num whitespace-nowrap text-right tabular-nums text-neutral-600">
                      {formatTenge(p.price_nonresident_kzt)}
                    </TD>
                    <TD className="whitespace-nowrap text-right">
                      {pct === null ? (
                        <span className="text-neutral-400">—</span>
                      ) : (
                        <span
                          className={
                            up
                              ? "inline-flex items-center justify-end gap-1 text-red-600"
                              : down
                                ? "inline-flex items-center justify-end gap-1 text-emerald-600"
                                : "inline-flex items-center justify-end gap-1 text-neutral-500"
                          }
                        >
                          {up && <TrendingUp className="h-3.5 w-3.5" />}
                          {down && <TrendingDown className="h-3.5 w-3.5" />}
                          {!up && !down && <Minus className="h-3.5 w-3.5" />}
                          <span className="num tabular-nums">
                            {up ? "+" : ""}
                            {Math.round(pct * 10) / 10}%
                          </span>
                        </span>
                      )}
                    </TD>
                    <TD className="max-w-[16rem]">
                      <span className="flex items-center gap-1.5 truncate text-neutral-700">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
                        <span className="truncate">{p.document_name}</span>
                      </span>
                    </TD>
                    <TD className="whitespace-nowrap uppercase text-neutral-500">
                      {p.file_format || "—"}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </div>
    </Card>
  );
}

export default function PartnerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const partnerId = id ?? "";

  // Шапка партнёра (берём из списка партнёров, отдельного эндпоинта нет).
  const [partner, setPartner] = useState<Partner | null>(null);
  const [headerLoading, setHeaderLoading] = useState(true);
  const [headerError, setHeaderError] = useState<string | null>(null);

  // Прайс лист.
  const [items, setItems] = useState<PriceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [activeOnly, setActiveOnly] = useState(true);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  // Выбранная строка для истории цен.
  const [selected, setSelected] = useState<PriceItem | null>(null);

  // Загрузка шапки.
  useEffect(() => {
    if (!partnerId) return;
    let alive = true;
    setHeaderLoading(true);
    setHeaderError(null);
    listPartners({ limit: 500, offset: 0 })
      .then((res) => {
        if (!alive) return;
        const found = res.items.find((p) => p.partner_id === partnerId) ?? null;
        setPartner(found);
        if (!found) setHeaderError("Партнёр не найден.");
      })
      .catch((e: unknown) => {
        if (alive)
          setHeaderError(e instanceof Error ? e.message : "Ошибка загрузки");
      })
      .finally(() => {
        if (alive) setHeaderLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [partnerId]);

  // Загрузка прайса с учётом пагинации и фильтра активности.
  const loadServices = useCallback(() => {
    if (!partnerId) return;
    let alive = true;
    setListLoading(true);
    setListError(null);
    getPartnerServices(partnerId, {
      active_only: activeOnly,
      limit: PAGE_SIZE,
      offset,
    })
      .then((res) => {
        if (!alive) return;
        setItems(res.items);
        setTotal(res.page.total);
      })
      .catch((e: unknown) => {
        if (alive)
          setListError(e instanceof Error ? e.message : "Ошибка загрузки");
      })
      .finally(() => {
        if (alive) setListLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [partnerId, activeOnly, offset]);

  useEffect(() => {
    const cleanup = loadServices();
    return cleanup;
  }, [loadServices]);

  // Сброс страницы при смене фильтра активности.
  function toggleActiveOnly() {
    setSelected(null);
    setOffset(0);
    setActiveOnly((v) => !v);
  }

  function openHistory(item: PriceItem) {
    if (!item.service_id) return;
    setSelected((cur) => (cur && cur.item_id === item.item_id ? null : item));
  }

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + items.length, total);
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <div className="flex flex-col gap-6">
      {/* Навигация назад */}
      <div>
        <Link
          to="/partners"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-500 transition-colors hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" />
          Все партнёры
        </Link>
      </div>

      {/* Шапка партнёра */}
      {headerLoading ? (
        <Card className="p-6">
          <Spinner label="Загрузка партнёра" />
        </Card>
      ) : headerError ? (
        <Card className="p-6">
          <div className="flex items-center gap-2 text-sm text-red-700">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{headerError}</span>
          </div>
        </Card>
      ) : partner ? (
        <Card className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-sm border border-line bg-neutral-50">
                  <Building2 className="h-5 w-5 text-accent" />
                </div>
                <div className="min-w-0">
                  <h1 className="truncate text-xl font-semibold tracking-tight text-ink">
                    {partner.name}
                  </h1>
                  <div className="mt-0.5 flex items-center gap-1.5 text-sm text-neutral-500">
                    <MapPin className="h-3.5 w-3.5" />
                    {partner.city || "Город не указан"}
                  </div>
                </div>
              </div>
            </div>
            <Badge tone={partner.is_active ? "success" : "neutral"}>
              {partner.is_active ? "Активен" : "Неактивен"}
            </Badge>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-x-8 gap-y-3 border-t border-line pt-5 sm:grid-cols-2">
            <div className="flex items-start gap-2 text-sm">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-neutral-400" />
              <span className="text-neutral-700">
                {partner.address || "Адрес не указан"}
              </span>
            </div>
            <div className="flex items-start gap-2 text-sm">
              <Hash className="mt-0.5 h-4 w-4 shrink-0 text-neutral-400" />
              <span className="num text-neutral-700 tabular-nums">
                {partner.bin || "БИН не указан"}
              </span>
            </div>
            <div className="flex items-start gap-2 text-sm">
              <Mail className="mt-0.5 h-4 w-4 shrink-0 text-neutral-400" />
              {partner.contact_email ? (
                <a
                  href={`mailto:${partner.contact_email}`}
                  className="text-accent hover:underline"
                >
                  {partner.contact_email}
                </a>
              ) : (
                <span className="text-neutral-500">Почта не указана</span>
              )}
            </div>
            <div className="flex items-start gap-2 text-sm">
              <Phone className="mt-0.5 h-4 w-4 shrink-0 text-neutral-400" />
              {partner.contact_phone ? (
                <a
                  href={`tel:${partner.contact_phone}`}
                  className="num text-neutral-700 tabular-nums hover:text-ink"
                >
                  {partner.contact_phone}
                </a>
              ) : (
                <span className="text-neutral-500">Телефон не указан</span>
              )}
            </div>
          </div>
        </Card>
      ) : null}

      {/* Панель истории цен (демонстрация версионирования) */}
      {selected && partner && (
        <HistoryPanel
          partnerId={partnerId}
          item={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {/* Прайс лист */}
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-ink">
              Прайс лист
            </h2>
            <p className="mt-0.5 text-sm text-neutral-500">
              Нажмите на сопоставленную строку, чтобы открыть историю цен.
            </p>
          </div>
          <Button
            size="sm"
            variant={activeOnly ? "primary" : "secondary"}
            onClick={toggleActiveOnly}
          >
            {activeOnly ? "Только активные" : "Все версии"}
          </Button>
        </div>

        {listLoading ? (
          <Card className="p-10">
            <Spinner label="Загрузка прайса" className="justify-center" />
          </Card>
        ) : listError ? (
          <Card className="p-6">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2 text-sm text-red-700">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{listError}</span>
              </div>
              <Button size="sm" variant="secondary" onClick={loadServices}>
                Повторить
              </Button>
            </div>
          </Card>
        ) : items.length === 0 ? (
          <EmptyState
            title="Прайс лист пуст"
            description="Для этого партнёра пока нет загруженных позиций прайса."
            icon={<FileText className="h-6 w-6" />}
          />
        ) : (
          <>
            <Table>
              <THead>
                <TR>
                  <TH>Услуга</TH>
                  <TH>Код</TH>
                  <TH className="text-right">Резидент</TH>
                  <TH className="text-right">Нерезидент</TH>
                  <TH className="whitespace-nowrap">Дата</TH>
                  <TH>Совпадение</TH>
                  <TH className="text-center">Аномалия</TH>
                  <TH aria-label="История" />
                </TR>
              </THead>
              <TBody>
                {items.map((item) => {
                  const clickable = Boolean(item.service_id);
                  const isOpen =
                    selected !== null && selected.item_id === item.item_id;
                  return (
                    <TR
                      key={item.item_id}
                      onClick={() => clickable && openHistory(item)}
                      className={
                        (clickable
                          ? "cursor-pointer hover:bg-neutral-50"
                          : "") + (isOpen ? " bg-accent/5" : "")
                      }
                    >
                      <TD className="max-w-[22rem]">
                        <div className="truncate font-medium text-ink">
                          {item.service_name_raw}
                        </div>
                        {item.category && (
                          <div className="truncate text-xs text-neutral-500">
                            {item.category}
                          </div>
                        )}
                        {clickable && (
                          <div className="mt-1">
                            <ConfidenceBar
                              value={item.match_confidence}
                              showValue
                            />
                          </div>
                        )}
                      </TD>
                      <TD className="num whitespace-nowrap tabular-nums text-neutral-500">
                        {item.service_code_source || "—"}
                      </TD>
                      <TD className="num whitespace-nowrap text-right tabular-nums font-medium">
                        {formatTenge(item.price_resident_kzt)}
                      </TD>
                      <TD className="num whitespace-nowrap text-right tabular-nums text-neutral-600">
                        {formatTenge(item.price_nonresident_kzt)}
                      </TD>
                      <TD className="whitespace-nowrap text-neutral-600">
                        {formatDate(item.effective_date)}
                      </TD>
                      <TD className="whitespace-nowrap">
                        <MatchBadge item={item} />
                      </TD>
                      <TD className="text-center">
                        {item.is_anomaly ? (
                          <Badge tone="danger">
                            <AlertTriangle className="h-3 w-3" />
                            Аномалия
                          </Badge>
                        ) : (
                          <span className="text-neutral-300">—</span>
                        )}
                      </TD>
                      <TD className="text-right">
                        {clickable ? (
                          <span className="inline-flex items-center text-neutral-400">
                            {isOpen ? (
                              <X className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </span>
                        ) : null}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>

            {/* Пагинация */}
            <div className="flex items-center justify-between gap-4 px-1">
              <div className="num text-sm text-neutral-500 tabular-nums">
                {pageStart}
                {" "}–{" "}
                {pageEnd} из {total}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!hasPrev}
                  onClick={() => {
                    setSelected(null);
                    setOffset((o) => Math.max(0, o - PAGE_SIZE));
                  }}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Назад
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!hasNext}
                  onClick={() => {
                    setSelected(null);
                    setOffset((o) => o + PAGE_SIZE);
                  }}
                >
                  Далее
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
