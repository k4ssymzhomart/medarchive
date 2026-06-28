// Список партнёров MedServicePrice.
// Фильтр по городу, фильтр по активности, пагинация. Строки ведут на /partners/:id.
// Острые углы, монохром плюс один акцент, иконки строго lucide-react.

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Building2,
  MapPin,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  Search,
} from "lucide-react";
import { listPartners } from "../lib/api";
import type { Page, Partner } from "../lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Spinner,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "../components/ui";

const PAGE_SIZE = 20;

type ActiveFilter = "all" | "active" | "inactive";

const ACTIVE_FILTERS: { value: ActiveFilter; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "active", label: "Активные" },
  { value: "inactive", label: "Неактивные" },
];

export default function PartnersPage() {
  // Черновик города в поле ввода и применённое значение фильтра.
  const [cityDraft, setCityDraft] = useState("");
  const [city, setCity] = useState("");
  const [active, setActive] = useState<ActiveFilter>("all");
  const [offset, setOffset] = useState(0);

  const [items, setItems] = useState<Partner[]>([]);
  const [page, setPage] = useState<Page | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const is_active =
      active === "all" ? undefined : active === "active" ? true : false;

    listPartners({
      city: city || undefined,
      is_active,
      limit: PAGE_SIZE,
      offset,
    })
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setPage(res.page);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Не удалось загрузить партнёров",
        );
        setItems([]);
        setPage(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [city, active, offset]);

  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  const pageInfo = useMemo(() => {
    if (loading) return "Загрузка";
    if (total === 0) return "Нет записей";
    return `${from} по ${to} из ${total}`;
  }, [loading, total, from, to]);

  function applyCity() {
    setOffset(0);
    setCity(cityDraft.trim());
  }

  function changeActive(value: ActiveFilter) {
    setOffset(0);
    setActive(value);
  }

  function resetFilters() {
    setCityDraft("");
    setCity("");
    setActive("all");
    setOffset(0);
  }

  const hasFilters = city !== "" || active !== "all";

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <div className="flex items-center gap-2 text-accent">
          <Building2 className="h-5 w-5" />
          <span className="text-xs font-medium uppercase tracking-wide">
            Каталог
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Партнёры
        </h1>
        <p className="text-sm text-neutral-500">
          Медицинские организации с загруженными прайс листами.
        </p>
      </header>

      <Card className="p-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="city"
              className="text-xs uppercase tracking-wide text-neutral-500"
            >
              Город
            </label>
            <div className="flex items-center gap-2">
              <div className="relative">
                <MapPin className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
                <input
                  id="city"
                  type="text"
                  value={cityDraft}
                  onChange={(e) => setCityDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") applyCity();
                  }}
                  placeholder="Например, Алматы"
                  className="h-10 w-56 rounded-sm border border-line bg-white pl-8 pr-3 text-sm text-ink outline-none placeholder:text-neutral-400 focus:border-accent"
                />
              </div>
              <Button variant="primary" size="md" onClick={applyCity}>
                <Search className="h-4 w-4" />
                Найти
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs uppercase tracking-wide text-neutral-500">
              Статус
            </span>
            <div className="flex items-center gap-2">
              <div className="inline-flex overflow-hidden rounded-sm border border-line">
                {ACTIVE_FILTERS.map((f, i) => {
                  const selected = active === f.value;
                  return (
                    <button
                      key={f.value}
                      type="button"
                      onClick={() => changeActive(f.value)}
                      className={[
                        "h-10 px-3 text-sm transition-colors",
                        i > 0 ? "border-l border-line" : "",
                        selected
                          ? "bg-accent text-white"
                          : "bg-white text-neutral-700 hover:bg-neutral-50",
                      ].join(" ")}
                    >
                      {f.label}
                    </button>
                  );
                })}
              </div>
              {hasFilters && (
                <Button variant="ghost" size="md" onClick={resetFilters}>
                  <RotateCw className="h-4 w-4" />
                  Сбросить
                </Button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {error ? (
        <Card className="p-0">
          <EmptyState
            className="border-0"
            icon={<Building2 className="h-8 w-8" />}
            title="Ошибка загрузки"
            description={error}
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  // Повторяем запрос, сбрасывая смещение на текущее значение.
                  setError(null);
                  setOffset((o) => o);
                  setCity((c) => c);
                }}
              >
                <RotateCw className="h-4 w-4" />
                Повторить
              </Button>
            }
          />
        </Card>
      ) : loading ? (
        <Card className="p-16">
          <Spinner label="Загрузка партнёров" className="justify-center" />
        </Card>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Building2 className="h-8 w-8" />}
          title="Партнёры не найдены"
          description={
            hasFilters
              ? "Попробуйте изменить фильтры или сбросить их."
              : "В каталоге пока нет ни одной организации."
          }
          action={
            hasFilters ? (
              <Button variant="secondary" onClick={resetFilters}>
                <RotateCw className="h-4 w-4" />
                Сбросить фильтры
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH className="w-[44%]">Название</TH>
              <TH className="w-[28%]">Город</TH>
              <TH className="w-[16%]">Статус</TH>
              <TH className="w-[12%] text-right">Открыть</TH>
            </TR>
          </THead>
          <TBody>
            {items.map((p) => (
              <TR key={p.partner_id} className="hover:bg-neutral-50">
                <TD>
                  <Link
                    to={`/app/partners/${encodeURIComponent(p.partner_id)}`}
                    className="flex items-center gap-2 font-medium text-ink hover:text-accent"
                  >
                    <Building2 className="h-4 w-4 shrink-0 text-neutral-400" />
                    <span className="truncate">{p.name}</span>
                  </Link>
                  {p.bin && (
                    <span className="num mt-0.5 block pl-6 text-xs tabular-nums text-neutral-400">
                      БИН {p.bin}
                    </span>
                  )}
                </TD>
                <TD>
                  <span className="inline-flex items-center gap-1.5 text-neutral-700">
                    <MapPin className="h-3.5 w-3.5 text-neutral-400" />
                    {p.city || "—"}
                  </span>
                </TD>
                <TD>
                  {p.is_active ? (
                    <Badge tone="success">Активен</Badge>
                  ) : (
                    <Badge tone="neutral">Неактивен</Badge>
                  )}
                </TD>
                <TD className="text-right">
                  <Link
                    to={`/app/partners/${encodeURIComponent(p.partner_id)}`}
                    className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
                  >
                    Детали
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      {!error && (items.length > 0 || hasPrev) && (
        <div className="flex items-center justify-between">
          <span className="num text-sm tabular-nums text-neutral-500">
            {pageInfo}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasPrev || loading}
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            >
              <ChevronLeft className="h-4 w-4" />
              Назад
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasNext || loading}
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
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
