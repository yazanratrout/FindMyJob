import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useAddEligibilityEntry,
  useAddTerm,
  useDeleteEligibilityEntry,
  useDeleteTerm,
  useEligibilityEntries,
  useEligibilityGauge,
  useSemesterTerms,
} from "@/api/hooks";
import { Button, Card, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";

function Gauge({
  used,
  limit,
}: {
  used: number;
  limit: number;
}) {
  const pct = Math.min(100, (used / limit) * 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span>{used} working days used this year</span>
        <span className="text-slate-400">limit {limit}</span>
      </div>
      <div className="h-3 rounded bg-slate-100">
        <div
          className={cn(
            "h-3 rounded",
            pct > 90 ? "bg-red-600" : pct > 70 ? "bg-amber-500" : "bg-slate-700",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function EligibilityPage() {
  const gauge = useEligibilityGauge();
  const entries = useEligibilityEntries();
  const addEntry = useAddEligibilityEntry();
  const delEntry = useDeleteEligibilityEntry();
  const terms = useSemesterTerms();
  const addTerm = useAddTerm();
  const delTerm = useDeleteTerm();

  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [dayType, setDayType] = useState<"full" | "half">("full");
  const [note, setNote] = useState("");

  const [tLabel, setTLabel] = useState("");
  const [tStart, setTStart] = useState("");
  const [tEnd, setTEnd] = useState("");

  if (gauge.isLoading) return <Spinner />;

  if (!gauge.data?.enabled) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Eligibility</h1>
        <Card>
          <p className="text-sm text-slate-600">
            The eligibility module is off. Turn it on under{" "}
            <Link to="/settings" className="underline">
              Settings → Eligibility
            </Link>{" "}
            if you are a non-EU/EEA student and want the 140/280 working-day
            tracker and the 20h-during-term check.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Eligibility</h1>

      <Card title={`Working days ${gauge.data.year}`}>
        <Gauge used={gauge.data.days_used} limit={gauge.data.limit_full_days} />
        <p className="mt-2 text-xs text-slate-400">
          Non-EU/EEA students may work 140 full days (or 280 half days) per
          calendar year without extra permission. This is guidance only — the
          Ausländerbehörde / your enrolment office is authoritative.
        </p>
      </Card>

      <Card title="Working-day ledger">
        <ul className="mb-3 space-y-1 text-sm">
          {(entries.data ?? []).map((e) => (
            <li key={e.id} className="flex items-center justify-between">
              <span>
                {e.period_start} → {e.period_end} · {e.day_count} {e.day_type}{" "}
                days{e.note && ` · ${e.note}`}
              </span>
              <Button variant="ghost" onClick={() => delEntry.mutate(e.id)}>
                Remove
              </Button>
            </li>
          ))}
          {entries.data?.length === 0 && (
            <li className="text-slate-400">No entries yet.</li>
          )}
        </ul>
        <div className="flex flex-wrap items-end gap-2">
          <input
            type="date"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
          <input
            type="date"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
          <select
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={dayType}
            onChange={(e) => setDayType(e.target.value as "full" | "half")}
          >
            <option value="full">full days</option>
            <option value="half">half days</option>
          </select>
          <input
            placeholder="note"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <Button
            variant="ghost"
            onClick={() => {
              if (start && end) {
                addEntry.mutate({
                  period_start: start,
                  period_end: end,
                  day_type: dayType,
                  note,
                });
                setStart("");
                setEnd("");
                setNote("");
              }
            }}
          >
            Add
          </Button>
        </div>
      </Card>

      <Card title="Lecture periods (for the 20h/week rule)">
        <ul className="mb-3 space-y-1 text-sm">
          {(terms.data ?? []).map((t) => (
            <li key={t.id} className="flex items-center justify-between">
              <span>
                {t.label}: {t.lecture_start} → {t.lecture_end}
              </span>
              <Button variant="ghost" onClick={() => delTerm.mutate(t.id)}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-end gap-2">
          <input
            placeholder="WS 2026/27"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={tLabel}
            onChange={(e) => setTLabel(e.target.value)}
          />
          <input
            type="date"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={tStart}
            onChange={(e) => setTStart(e.target.value)}
          />
          <input
            type="date"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={tEnd}
            onChange={(e) => setTEnd(e.target.value)}
          />
          <Button
            variant="ghost"
            onClick={() => {
              if (tLabel && tStart && tEnd) {
                addTerm.mutate({
                  label: tLabel,
                  lecture_start: tStart,
                  lecture_end: tEnd,
                });
                setTLabel("");
                setTStart("");
                setTEnd("");
              }
            }}
          >
            Add
          </Button>
        </div>
      </Card>
    </div>
  );
}
