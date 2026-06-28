// Типизированный клиент API MedServicePrice.
// База берётся из VITE_API_URL, иначе прокси "/api" (см. vite.config.ts / nginx.conf).

const BASE = (import.meta.env.VITE_API_URL as string) || "/api";

// Операторский токен для админских эндпоинтов (загрузка, сопоставление, очереди).
// Пусто -> заголовок не шлётся (открытый dev-контур). Значение вшивается в сборку
// (VITE_*), поэтому это НЕ секрет, а токен демо-оператора: deter casual access, но
// он публичен в бандле. Шлём на все запросы; на публичных роутах бэкенд игнорирует.
const OPERATOR_TOKEN = (import.meta.env.VITE_OPERATOR_TOKEN as string) || "";

// --- Общие типы ---

export interface Page {
  total: number;
  limit: number;
  offset: number;
}

export type ParseStatus =
  | "pending"
  | "processing"
  | "done"
  | "error"
  | "needs_review";

export type MatchAction = "confirm" | "reject" | "correct";

export type SearchKind = "service" | "partner";

export type UnmatchedMode = "all" | "unmatched" | "needs_review" | "anomaly";

// --- Доменные модели ---

export interface Service {
  service_id: string;
  service_name: string;
  synonyms: string[];
  category: string;
  icd_code: string;
  is_active: boolean;
}

export interface ServicePartner {
  partner_id: string;
  partner_name: string;
  city: string;
  price_resident_kzt: number | null;
  price_nonresident_kzt: number | null;
  effective_date: string | null;
  item_id: string;
}

export interface Partner {
  partner_id: string;
  name: string;
  city: string;
  address: string;
  bin: string;
  contact_email: string;
  contact_phone: string;
  is_active: boolean;
}

export interface PriceItem {
  item_id: string;
  doc_id: string;
  partner_id: string;
  service_id: string | null;
  service_name_raw: string;
  service_code_source: string;
  price_resident_kzt: number | null;
  price_nonresident_kzt: number | null;
  price_original: number | null;
  currency_original: string;
  is_verified: boolean;
  verification_note: string;
  effective_date: string | null;
  is_active: boolean;
  match_confidence: number | null;
  match_method: string;
  source_page: number | null;
  source_row: number | null;
  raw_price_label: string;
  category: string;
  needs_review: boolean;
  is_anomaly: boolean;
}

export interface HistoryPoint {
  item_id: string;
  effective_date: string | null;
  price_resident_kzt: number | null;
  price_nonresident_kzt: number | null;
  is_active: boolean;
  document_name: string;
  file_format: string;
  pct_change: number | null;
}

export interface PriceHistory {
  partner_id: string;
  service_id: string;
  service_name: string;
  points: HistoryPoint[];
}

export interface SearchResult {
  kind: SearchKind;
  id: string;
  title: string;
  subtitle: string;
  category: string;
  rank: number;
}

export interface SearchResponse {
  query: string;
  took_ms: number;
  total: number;
  results: SearchResult[];
}

export interface MatchCandidate {
  service_id: string;
  service_name: string;
  score: number;
  method: string;
  rank: number;
}

export interface UnmatchedItem extends PriceItem {
  partner_name: string;
  document_name: string;
  candidates: MatchCandidate[];
}

export interface MatchResponse {
  item_id: string;
  service_id: string | null;
  match_method: string;
  match_confidence: number | null;
  is_verified: boolean;
  synonyms_learned: number;
}

export interface Document {
  doc_id: string;
  partner_id: string;
  file_name: string;
  file_format: string;
  effective_date: string | null;
  parse_status: ParseStatus;
  parse_log: string;
  page_count: number | null;
  extractor_used: string;
  ocr_applied: boolean;
  item_count: number;
  processing_seconds: number | null;
  parsed_at: string | null;
}

export interface UploadResponse {
  documents: Document[];
  skipped_duplicates: string[];
  message: string;
}

export interface DocumentStatus {
  doc_id: string;
  file_name: string;
  parse_status: ParseStatus;
  item_count: number;
  ocr_applied: boolean;
  processing_seconds: number | null;
  parse_log: string;
}

export interface FormatStat {
  file_format: string;
  documents: number;
  items: number;
  matched: number;
  match_rate: number;
}

export interface PartnerStat {
  partner: string;
  items: number;
  matched: number;
  match_rate: number;
}

export interface Stats {
  documents_total: number;
  documents_by_status: Record<string, number>;
  items_total: number;
  items_active: number;
  items_matched: number;
  match_rate: number;
  needs_review_count: number;
  unmatched_count: number;
  anomaly_count: number;
  by_format: FormatStat[];
  by_partner: PartnerStat[];
  avg_processing_seconds: number | null;
  services_total: number;
  partners_total: number;
}

// --- Параметры списков ---

export interface ListServicesParams {
  category?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface ListPartnersParams {
  city?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}

export interface PartnerServicesParams {
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export interface SearchParams {
  q: string;
  limit?: number;
  offset?: number;
}

export interface UnmatchedParams {
  mode?: UnmatchedMode;
  limit?: number;
  offset?: number;
}

export interface MatchPayload {
  item_id: string;
  service_id: string | null;
  action: MatchAction;
  note?: string;
}

// --- Низкоуровневый fetch ---

function buildQuery(params: object | undefined): string {
  if (!params) return "";
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    usp.set(key, String(value));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (OPERATOR_TOKEN) {
    headers.Authorization = `Bearer ${OPERATOR_TOKEN}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers, ...((init?.headers as Record<string, string>) ?? {}) },
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      detail = "";
    }
    throw new Error(
      `Запрос ${path} завершился ошибкой ${res.status}${detail ? `: ${detail}` : ""}`,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Услуги ---

export function listServices(
  params?: ListServicesParams,
): Promise<{ page: Page; items: Service[] }> {
  return request(`/services${buildQuery(params)}`);
}

export function getServicePartners(
  serviceId: string,
): Promise<ServicePartner[]> {
  return request(`/services/${encodeURIComponent(serviceId)}/partners`);
}

// --- Партнёры ---

export function listPartners(
  params?: ListPartnersParams,
): Promise<{ page: Page; items: Partner[] }> {
  return request(`/partners${buildQuery(params)}`);
}

export function getPartnerServices(
  partnerId: string,
  params?: PartnerServicesParams,
): Promise<{ page: Page; items: PriceItem[] }> {
  return request(
    `/partners/${encodeURIComponent(partnerId)}/services${buildQuery(params)}`,
  );
}

export function getPriceHistory(
  partnerId: string,
  serviceId: string,
): Promise<PriceHistory> {
  return request(
    `/partners/${encodeURIComponent(partnerId)}/services/${encodeURIComponent(
      serviceId,
    )}/history`,
  );
}

// --- Поиск ---

export function search(params: SearchParams): Promise<SearchResponse> {
  return request(`/search${buildQuery(params)}`);
}

// --- Сопоставление ---

export function listUnmatched(
  params?: UnmatchedParams,
): Promise<{ page: Page; items: UnmatchedItem[] }> {
  return request(`/unmatched${buildQuery(params)}`);
}

export function postMatch(payload: MatchPayload): Promise<MatchResponse> {
  return request(`/match`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- Документы / загрузка ---

export function uploadFile(
  file: File,
  enqueue = true,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request(`/upload${buildQuery({ enqueue })}`, {
    method: "POST",
    body: form,
  });
}

export function listDocuments(status?: ParseStatus): Promise<Document[]> {
  return request(`/documents${buildQuery({ status })}`);
}

export function getDocumentStatus(docId: string): Promise<DocumentStatus> {
  return request(`/documents/${encodeURIComponent(docId)}/status`);
}

// --- Статистика ---

export function getStats(): Promise<Stats> {
  return request(`/stats`);
}
