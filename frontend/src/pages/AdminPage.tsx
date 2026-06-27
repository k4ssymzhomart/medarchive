// Страница администратора: загрузка прайс листов и статусы обработки документов.
// Drop control принимает .zip или одиночный файл прайса. После загрузки список
// документов опрашивается каждые 2 секунды, пока есть документы в обработке.

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  Upload,
  FileText,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Loader2,
  ScanLine,
  Inbox,
  CircleAlert,
} from "lucide-react";

import {
  uploadFile,
  listDocuments,
  type Document,
  type ParseStatus,
  type UploadResponse,
} from "../lib/api";
import { formatDate, statusLabel } from "../lib/format";
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
} from "../components/ui";

// --- Вспомогательные функции отображения ---

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

const STATUS_TONE: Record<ParseStatus, BadgeTone> = {
  pending: "neutral",
  processing: "accent",
  done: "success",
  error: "danger",
  needs_review: "warning",
};

function StatusBadge({ status }: { status: ParseStatus }) {
  const tone = STATUS_TONE[status] ?? "neutral";
  const Icon =
    status === "done"
      ? CheckCircle2
      : status === "error"
        ? XCircle
        : status === "needs_review"
          ? AlertTriangle
          : status === "processing"
            ? Loader2
            : Clock;
  return (
    <Badge tone={tone}>
      <Icon
        className={
          status === "processing" ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"
        }
      />
      {statusLabel(status)}
    </Badge>
  );
}

// Секунды обработки в читаемую строку без дефисов.
function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 1) return `${(value).toFixed(2)} с`;
  if (value < 60) return `${value.toFixed(1)} с`;
  const m = Math.floor(value / 60);
  const s = Math.round(value % 60);
  return `${m} мин ${s} с`;
}

// Формат файла в верхнем регистре, без точки.
function formatLabel(fmt: string): string {
  const clean = (fmt || "").replace(/^\./, "").trim();
  return clean ? clean.toUpperCase() : "—";
}

const ACTIVE_STATUSES: ParseStatus[] = ["pending", "processing"];

function hasActive(docs: Document[]): boolean {
  return docs.some((d) => ACTIVE_STATUSES.includes(d.parse_status));
}

// Допустимые расширения для drop control.
const ACCEPT =
  ".zip,.xlsx,.xls,.csv,.pdf,.docx,.doc,.png,.jpg,.jpeg,.tiff,.tif";

// --- Основной компонент ---

export default function AdminPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastUpload, setLastUpload] = useState<UploadResponse | null>(null);

  const [dragOver, setDragOver] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const inputRef = useRef<HTMLInputElement | null>(null);
  const pollRef = useRef<number | null>(null);

  // Загрузка списка документов с бэкенда.
  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Не удалось загрузить документы");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Первая загрузка.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Опрос каждые 2 секунды, пока есть документы в очереди или обработке.
  const polling = useMemo(() => hasActive(documents), [documents]);

  useEffect(() => {
    if (!polling) {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = window.setInterval(() => {
      void refresh(true);
    }, 2000);
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [polling, refresh]);

  // Отправка файла на сервер.
  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      setUploading(true);
      setUploadError(null);
      try {
        const res = await uploadFile(file, true);
        setLastUpload(res);
        await refresh(true);
      } catch (err) {
        setUploadError(
          err instanceof Error ? err.message : "Не удалось загрузить файл",
        );
      } finally {
        setUploading(false);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [refresh],
  );

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    void handleFiles(e.target.files);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (uploading) return;
    void handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!dragOver) setDragOver(true);
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
  };

  const toggleExpanded = (docId: string) => {
    setExpanded((prev) => ({ ...prev, [docId]: !prev[docId] }));
  };

  const activeCount = useMemo(
    () => documents.filter((d) => ACTIVE_STATUSES.includes(d.parse_status)).length,
    [documents],
  );

  return (
    <div className="flex flex-col gap-8">
      {/* Заголовок раздела */}
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Загрузка прайс листов
        </h1>
        <p className="max-w-2xl text-sm text-neutral-500">
          Загрузите архив .zip с несколькими прайсами или одиночный файл прайса.
          После загрузки документы автоматически обрабатываются, а статусы
          обновляются каждые 2 секунды.
        </p>
      </header>

      {/* Drop control */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        role="button"
        tabIndex={0}
        onClick={() => {
          if (!uploading) inputRef.current?.click();
        }}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !uploading) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={[
          "flex flex-col items-center justify-center gap-3 rounded-sm border border-dashed bg-white px-6 py-14 text-center transition-colors",
          dragOver
            ? "border-accent bg-accent/5"
            : "border-line hover:border-neutral-400",
          uploading ? "cursor-wait opacity-70" : "cursor-pointer",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={onInputChange}
          disabled={uploading}
        />
        {uploading ? (
          <Spinner label="Загрузка файла" />
        ) : (
          <>
            <div className="text-neutral-400">
              <Upload className="h-8 w-8" />
            </div>
            <div className="text-base font-medium text-ink">
              Перетащите файл сюда или нажмите для выбора
            </div>
            <div className="max-w-md text-sm text-neutral-500">
              Поддерживаются архивы .zip и одиночные прайсы в форматах XLSX, CSV,
              PDF, DOCX и изображения для распознавания.
            </div>
            <Button variant="primary" size="sm" className="mt-1">
              <Upload className="h-4 w-4" />
              Выбрать файл
            </Button>
          </>
        )}
      </div>

      {/* Ошибка загрузки */}
      {uploadError && (
        <Card className="flex items-start gap-3 border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-medium">Ошибка при загрузке</div>
            <div className="mt-1 text-red-600">{uploadError}</div>
          </div>
        </Card>
      )}

      {/* Итог последней загрузки */}
      {lastUpload && (
        <Card className="flex flex-col gap-3 p-4">
          <div className="flex items-start gap-3 text-sm">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            <div className="flex flex-col gap-1">
              <div className="font-medium text-ink">
                {lastUpload.message || "Загрузка принята"}
              </div>
              <div className="text-neutral-500">
                Добавлено документов: {lastUpload.documents.length}
              </div>
            </div>
          </div>

          {lastUpload.skipped_duplicates.length > 0 && (
            <div className="flex items-start gap-3 rounded-sm border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="font-medium">
                  Пропущены дубликаты ({lastUpload.skipped_duplicates.length})
                </div>
                <ul className="mt-1 flex flex-col gap-0.5 text-amber-600">
                  {lastUpload.skipped_duplicates.map((name) => (
                    <li key={name} className="truncate">
                      {name}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Список документов */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight text-ink">
              Документы
            </h2>
            {polling && (
              <span className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />В обработке:{" "}
                {activeCount}
              </span>
            )}
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void refresh()}
            disabled={loading}
          >
            <RefreshCw
              className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"}
            />
            Обновить
          </Button>
        </div>

        {listError && (
          <Card className="flex items-start gap-3 border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <div className="font-medium">Не удалось загрузить список</div>
              <div className="mt-1 text-red-600">{listError}</div>
            </div>
          </Card>
        )}

        {loading && documents.length === 0 ? (
          <div className="py-16">
            <Spinner label="Загрузка документов" className="justify-center" />
          </div>
        ) : documents.length === 0 && !listError ? (
          <EmptyState
            title="Пока нет документов"
            description="Загрузите первый прайс лист, чтобы увидеть статусы обработки."
            icon={<Inbox className="h-8 w-8" />}
          />
        ) : documents.length > 0 ? (
          <Table>
            <THead>
              <TR>
                <TH className="w-8" />
                <TH>Файл</TH>
                <TH>Формат</TH>
                <TH>Дата прайса</TH>
                <TH>Статус</TH>
                <TH className="text-right">Позиций</TH>
                <TH>Распознавание</TH>
                <TH className="text-right">Время</TH>
              </TR>
            </THead>
            <TBody>
              {documents.map((doc) => {
                const isOpen = !!expanded[doc.doc_id];
                const hasLog = !!doc.parse_log && doc.parse_log.trim().length > 0;
                return (
                  <DocumentRow
                    key={doc.doc_id}
                    doc={doc}
                    isOpen={isOpen}
                    hasLog={hasLog}
                    onToggle={() => toggleExpanded(doc.doc_id)}
                  />
                );
              })}
            </TBody>
          </Table>
        ) : null}
      </section>
    </div>
  );
}

// --- Строка таблицы с раскрываемым журналом разбора ---

interface DocumentRowProps {
  doc: Document;
  isOpen: boolean;
  hasLog: boolean;
  onToggle: () => void;
}

function DocumentRow({ doc, isOpen, hasLog, onToggle }: DocumentRowProps) {
  return (
    <>
      <TR
        className={hasLog ? "cursor-pointer hover:bg-neutral-50" : undefined}
        onClick={hasLog ? onToggle : undefined}
      >
        <TD className="text-neutral-400">
          {hasLog ? (
            isOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )
          ) : null}
        </TD>
        <TD>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 shrink-0 text-neutral-400" />
            <span className="font-medium text-ink">{doc.file_name}</span>
          </div>
          {doc.extractor_used && (
            <div className="mt-0.5 pl-6 text-xs text-neutral-400">
              {doc.extractor_used}
            </div>
          )}
        </TD>
        <TD>
          <Badge tone="neutral">{formatLabel(doc.file_format)}</Badge>
        </TD>
        <TD className="num whitespace-nowrap tabular-nums text-neutral-700">
          {formatDate(doc.effective_date)}
        </TD>
        <TD>
          <StatusBadge status={doc.parse_status} />
        </TD>
        <TD className="num text-right tabular-nums text-ink">
          {doc.item_count}
        </TD>
        <TD>
          {doc.ocr_applied ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-neutral-700">
              <ScanLine className="h-4 w-4 text-accent" />
              Применено
            </span>
          ) : (
            <span className="text-sm text-neutral-400">Нет</span>
          )}
        </TD>
        <TD className="num whitespace-nowrap text-right tabular-nums text-neutral-700">
          {formatSeconds(doc.processing_seconds)}
        </TD>
      </TR>

      {isOpen && hasLog && (
        <TR className="bg-neutral-50">
          <TD />
          <TD colSpan={7}>
            <div className="flex flex-col gap-2 py-1">
              <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                Журнал разбора
              </div>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-sm border border-line bg-white p-3 text-xs leading-relaxed text-neutral-700">
                {doc.parse_log}
              </pre>
              {doc.page_count !== null && (
                <div className="text-xs text-neutral-400">
                  Страниц в документе: {doc.page_count}
                </div>
              )}
            </div>
          </TD>
        </TR>
      )}
    </>
  );
}
