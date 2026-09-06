/**
 * The shared UI kit. Everything visual in the app is built from these pieces so
 * spacing, colour and states stay consistent. No app/domain logic lives here.
 */
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TextareaHTMLAttributes,
} from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ Button */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  icon: Icon,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const variants: Record<ButtonVariant, string> = {
    primary:
      "bg-slate-900 text-white hover:bg-slate-700 disabled:bg-slate-300 disabled:text-slate-500",
    secondary:
      "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400",
    ghost: "text-slate-600 hover:bg-slate-100 disabled:text-slate-400",
    danger: "bg-red-600 text-white hover:bg-red-500 disabled:bg-red-300",
  };
  const sizes: Record<ButtonSize, string> = {
    sm: "gap-1.5 px-2.5 py-1.5 text-xs",
    md: "gap-2 px-3.5 py-2 text-sm",
  };
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center rounded-lg font-medium transition-colors",
        "focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none",
        "disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : Icon ? (
        <Icon className="h-4 w-4" />
      ) : null}
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ Inputs */

const fieldStyles =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 " +
  "placeholder:text-slate-400 focus:border-slate-500 focus:ring-1 focus:ring-slate-500 focus:outline-none";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldStyles, className)} {...props} />;
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldStyles, "resize-y", className)} {...props} />;
}

/* -------------------------------------------------------------------- Card */

export function Card({
  title,
  action,
  children,
  className,
  padded = true,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-slate-200 bg-white shadow-sm",
        padded && "p-5",
        className,
      )}
    >
      {(title != null || action != null) && (
        <header className={cn("mb-4 flex items-center justify-between gap-3", !padded && "p-5 pb-0")}>
          {title != null && (
            <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase">
              {title}
            </h2>
          )}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------- Badge */

type Tone = "neutral" | "good" | "warn" | "bad" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-600 ring-slate-200",
  good: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warn: "bg-amber-50 text-amber-700 ring-amber-200",
  bad: "bg-red-50 text-red-700 ring-red-200",
  info: "bg-indigo-50 text-indigo-700 ring-indigo-200",
};

export function Badge({
  tone = "neutral",
  children,
  className,
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** The decision buckets get a fixed, learnable colour across the whole app. */
export const DECISION_TONE: Record<string, Tone> = {
  recommended: "good",
  maybe: "warn",
  archived: "neutral",
};

/* -------------------------------------------------------------- Score ring */

/** 0-100 match score. Colour matches the decision bands, size is fixed-width so
 *  rows stay aligned. */
export function ScoreRing({
  value,
  size = "md",
  label,
}: {
  value: number;
  size?: "sm" | "md" | "lg";
  label?: string;
}) {
  const pct = Math.max(0, Math.min(100, value));
  const colour =
    pct >= 70 ? "#059669" : pct >= 50 ? "#d97706" : "#94a3b8"; // emerald / amber / slate
  const dims = { sm: 36, md: 48, lg: 64 }[size];
  const stroke = size === "sm" ? 3 : 4;
  const r = (dims - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <div
      className="relative shrink-0"
      style={{ width: dims, height: dims }}
      title={label ?? `Match score ${Math.round(pct)} / 100`}
    >
      <svg width={dims} height={dims} className="-rotate-90">
        <circle
          cx={dims / 2}
          cy={dims / 2}
          r={r}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={stroke}
        />
        <circle
          cx={dims / 2}
          cy={dims / 2}
          r={r}
          fill="none"
          stroke={colour}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct / 100)}
          className="transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center font-bold text-slate-800",
          size === "sm" ? "text-[11px]" : size === "lg" ? "text-lg" : "text-sm",
        )}
      >
        {Math.round(pct)}
      </span>
    </div>
  );
}

/* ---------------------------------------------------------------- Meter bar */

export function Meter({
  value,
  tone = "neutral",
  className,
}: {
  value: number; // 0..1
  tone?: Tone;
  className?: string;
}) {
  const bar: Record<Tone, string> = {
    neutral: "bg-slate-400",
    good: "bg-emerald-500",
    warn: "bg-amber-500",
    bad: "bg-red-500",
    info: "bg-indigo-500",
  };
  return (
    <div className={cn("h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100", className)}>
      <div
        className={cn("h-full rounded-full transition-[width] duration-500", bar[tone])}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  );
}

/* --------------------------------------------------------------------- Stat */

export function Stat({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  tone?: Tone;
}) {
  const accent: Record<Tone, string> = {
    neutral: "text-slate-400",
    good: "text-emerald-600",
    warn: "text-amber-600",
    bad: "text-red-600",
    info: "text-indigo-600",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
        {Icon && <Icon className={cn("h-4 w-4", accent[tone])} />}
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
      {hint != null && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

/* --------------------------------------------------------------------- Tabs */

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: { key: T; label: string; count?: number }[];
  active: T;
  onChange: (key: T) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex gap-1 border-b border-slate-200", className)} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            active === t.key
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700",
          )}
        >
          {t.label}
          {t.count != null && (
            <span className="ml-1.5 text-xs text-slate-400">{t.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------- Chip / filters */

export function Chip({
  active,
  children,
  onClick,
  count,
}: {
  active?: boolean;
  children: ReactNode;
  onClick?: () => void;
  count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-slate-900 text-white"
          : "bg-white text-slate-600 ring-1 ring-slate-200 ring-inset hover:bg-slate-50",
      )}
    >
      {children}
      {count != null && (
        <span className={cn("text-xs", active ? "text-slate-300" : "text-slate-400")}>
          {count}
        </span>
      )}
    </button>
  );
}

/* -------------------------------------------------------- States & feedback */

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 p-8 text-sm text-slate-400">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-slate-200", className)} />;
}

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
      {Icon && <Icon className="mb-3 h-8 w-8 text-slate-300" />}
      <p className="font-medium text-slate-700">{title}</p>
      {children != null && (
        <div className="mt-1 max-w-md text-sm text-slate-500">{children}</div>
      )}
      {action != null && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
      {message}
    </div>
  );
}

export function Callout({
  tone = "info",
  icon: Icon,
  children,
}: {
  tone?: Tone;
  icon?: React.ComponentType<{ className?: string }>;
  children: ReactNode;
}) {
  const tones: Record<Tone, string> = {
    neutral: "border-slate-200 bg-slate-50 text-slate-700",
    good: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warn: "border-amber-200 bg-amber-50 text-amber-800",
    bad: "border-red-200 bg-red-50 text-red-800",
    info: "border-indigo-200 bg-indigo-50 text-indigo-800",
  };
  return (
    <div className={cn("flex gap-2 rounded-lg border p-3 text-sm", tones[tone])}>
      {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" />}
      <div className="min-w-0">{children}</div>
    </div>
  );
}
