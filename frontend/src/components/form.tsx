import {
  type ReactNode,
  type SelectHTMLAttributes,
  useState,
} from "react";
import { cn } from "@/lib/cn";
import { Input } from "./ui";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

export function Select({
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500",
        className,
      )}
      {...props}
    />
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-slate-300"
      />
      {label}
    </label>
  );
}

export function TagInput({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft("");
  };
  return (
    <div className="rounded-md border border-slate-300 bg-white p-2">
      <div className="flex flex-wrap gap-1">
        {values.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs"
          >
            {v}
            <button
              type="button"
              className="text-slate-400 hover:text-slate-700"
              onClick={() => onChange(values.filter((x) => x !== v))}
            >
              ×
            </button>
          </span>
        ))}
        <Input
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add();
            }
          }}
          onBlur={add}
          className="min-w-32 flex-1 border-0 p-1 focus:ring-0"
        />
      </div>
    </div>
  );
}

export function ChipToggle({
  options,
  values,
  onChange,
}: {
  options: Array<{ value: string; label: string }>;
  values: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (v: string) =>
    onChange(values.includes(v) ? values.filter((x) => x !== v) : [...values, v]);
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => toggle(o.value)}
          className={cn(
            "rounded-full border px-3 py-1 text-sm",
            values.includes(o.value)
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-300 bg-white text-slate-600 hover:border-slate-400",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
