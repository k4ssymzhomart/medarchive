// Общие UI примитивы MedPartners.
// Острые углы, монохром плюс один акцент, иконки строго lucide-react.

import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  ReactNode,
  TdHTMLAttributes,
  ThHTMLAttributes,
} from "react";
import { Loader2 } from "lucide-react";

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// --- Button ---

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-sm border font-medium transition-colors select-none disabled:opacity-40 disabled:cursor-not-allowed";
  const sizes: Record<ButtonSize, string> = {
    sm: "h-8 px-3 text-sm",
    md: "h-10 px-4 text-sm",
  };
  const variants: Record<ButtonVariant, string> = {
    primary:
      "border-accent bg-accent text-white hover:bg-[#173BD6] active:bg-[#1230B0]",
    secondary:
      "border-line bg-white text-ink hover:bg-neutral-50 active:bg-neutral-100",
    ghost: "border-transparent bg-transparent text-ink hover:bg-neutral-100",
    danger:
      "border-red-600 bg-white text-red-600 hover:bg-red-50 active:bg-red-100",
  };
  return (
    <button
      className={cx(base, sizes[size], variants[variant], className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

// --- Card ---

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div
      className={cx("rounded-sm border border-line bg-white", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

// --- Badge ---

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  children: ReactNode;
}

export function Badge({
  tone = "neutral",
  className,
  children,
  ...rest
}: BadgeProps) {
  const tones: Record<BadgeTone, string> = {
    neutral: "border-line bg-white text-neutral-700",
    accent: "border-accent/30 bg-accent/5 text-accent",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    danger: "border-red-200 bg-red-50 text-red-700",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-medium leading-5",
        tones[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

// --- Table ---

interface TableProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Table({ className, children, ...rest }: TableProps) {
  return (
    <div
      className={cx("overflow-x-auto rounded-sm border border-line", className)}
      {...rest}
    >
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-line bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500">
      {children}
    </thead>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TR({
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cx("border-b border-line last:border-0", className)}
      {...rest}
    >
      {children}
    </tr>
  );
}

export function TH({
  className,
  children,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cx("px-3 py-2 font-medium", className)}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TD({
  className,
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cx("px-3 py-2 align-middle", className)} {...rest}>
      {children}
    </td>
  );
}

// --- Stat ---

interface StatProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}

export function Stat({ label, value, hint, className }: StatProps) {
  return (
    <Card className={cx("p-4", className)}>
      <div className="text-xs uppercase tracking-wide text-neutral-500">
        {label}
      </div>
      <div className="num mt-2 text-2xl font-semibold text-ink">{value}</div>
      {hint && <div className="mt-1 text-xs text-neutral-500">{hint}</div>}
    </Card>
  );
}

// --- Spinner ---

interface SpinnerProps {
  className?: string;
  label?: string;
}

export function Spinner({ className, label }: SpinnerProps) {
  return (
    <div
      className={cx(
        "flex items-center gap-2 text-sm text-neutral-500",
        className,
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin" />
      {label && <span>{label}</span>}
    </div>
  );
}

// --- EmptyState ---

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-line bg-white px-6 py-16 text-center",
        className,
      )}
    >
      {icon && <div className="text-neutral-400">{icon}</div>}
      <div className="text-base font-medium text-ink">{title}</div>
      {description && (
        <div className="max-w-md text-sm text-neutral-500">{description}</div>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

// --- ConfidenceBar ---

interface ConfidenceBarProps {
  // Значение уверенности от 0 до 1.
  value: number | null | undefined;
  className?: string;
  showValue?: boolean;
}

export function ConfidenceBar({
  value,
  className,
  showValue = true,
}: ConfidenceBarProps) {
  const v =
    value === null || value === undefined || Number.isNaN(value)
      ? 0
      : Math.max(0, Math.min(1, value));
  const pct = Math.round(v * 100);
  // Цвет шкалы зависит от диапазона уверенности (пороги раздела 8.3).
  const fill =
    v >= 0.85 ? "bg-emerald-500" : v >= 0.6 ? "bg-amber-500" : "bg-red-500";
  const empty = value === null || value === undefined;
  return (
    <div className={cx("flex items-center gap-2", className)}>
      <div className="h-2 w-24 overflow-hidden rounded-sm border border-line bg-neutral-100">
        {!empty && (
          <div
            className={cx("h-full", fill)}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {showValue && (
        <span className="num w-9 text-right text-xs tabular-nums text-neutral-600">
          {empty ? "—" : `${pct}%`}
        </span>
      )}
    </div>
  );
}
