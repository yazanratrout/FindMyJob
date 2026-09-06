import { useState } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Loader2,
  MinusCircle,
  X,
  XCircle,
} from "lucide-react";
import { useRunDetail, useRuns } from "@/api/hooks";
import type { StageResult } from "@/api/types";
import {
  Badge,
  Card,
  EmptyState,
  ErrorBox,
  Skeleton,
  Spinner,
  Stat,
} from "@/components/ui";
import { cn } from "@/lib/cn";

const STAGE_HELP: Record<string, string> = {
  fetch: "Query every enabled job source",
  normalize: "Canonical shape + company resolution",
  enrich: "Fetch full descriptions (robots-aware)",
  dedup: "Link repeats to one canonical posting",
  prefilter: "Cheap deterministic filters — before any LLM call",
  analyze: "LLM extraction of the posting's facts",
  score: "Hard checks + weighted rules score",
  judge: "LLM holistic fit, blended into the final score",
  decide: "Which of your documents each job needs",
  notify: "Build the in-app digest",
};

function StatusIcon({ status }: { status: string }) {
  const map: Record<string, { Icon: typeof CheckCircle2; className: string }> = {
    ok: { Icon: CheckCircle2, className: "text-emerald-600" },
    completed: { Icon: CheckCircle2, className: "text-emerald-600" },
    partial: { Icon: AlertTriangle, className: "text-amber-500" },
    failed: { Icon: XCircle, className: "text-red-600" },
    skipped: { Icon: MinusCircle, className: "text-slate-300" },
    running: { Icon: Loader2, className: "animate-spin text-indigo-500" },
  };
  const { Icon, className } = map[status] ?? map.skipped;
  return <Icon className={cn("h-4 w-4 shrink-0", className)} />;
}

function StageRow({ stage }: { stage: StageResult }) {
  const stats = Object.entries(stage.stats);
  return (
    <li className="flex items-start gap-3 border-t border-slate-100 py-2.5 first:border-0">
      <StatusIcon status={stage.status} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-slate-800">{stage.name}</span>
          <span className="text-xs text-slate-400">
            {stage.duration_s.toFixed(2)}s
          </span>
          {stage.error_count > 0 && (
            <Badge tone="warn">{stage.error_count} errors</Badge>
          )}
        </div>
        <p className="text-xs text-slate-400">{STAGE_HELP[stage.name] ?? ""}</p>
        {stats.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {stats.map(([k, v]) => (
              <span
                key={k}
                className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600"
              >
                {k} <span className="font-semibold">{String(v)}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

function RunDetailDrawer({
  runId,
  onClose,
}: {
  runId: number | null;
  onClose: () => void;
}) {
  const detail = useRunDetail(runId);
  if (runId == null) return null;
  const d = detail.data;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-slate-900/30 backdrop-blur-[1px]"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {detail.isLoading ? (
          <Spinner />
        ) : detail.error || !d ? (
          <div className="p-6">
            <ErrorBox message="Could not load this run." />
          </div>
        ) : (
          <>
            <header className="flex items-start justify-between border-b border-slate-200 p-6">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold">Run #{d.run.id}</h2>
                  <StatusIcon status={d.run.status} />
                  <Badge
                    tone={
                      d.run.status === "completed"
                        ? "good"
                        : d.run.status === "failed"
                          ? "bad"
                          : "info"
                    }
                  >
                    {d.run.status}
                  </Badge>
                  <Badge tone="neutral">{d.run.trigger}</Badge>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {new Date(d.run.started_at).toLocaleString()}
                  {d.run.finished_at &&
                    ` → ${new Date(d.run.finished_at).toLocaleTimeString()}`}
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </header>

            <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
              <div className="grid grid-cols-3 gap-3">
                <Stat label="LLM calls" value={d.llm.calls} />
                <Stat label="Cache hits" value={d.llm.cache_hits} hint="free repeats" />
                <Stat label="Cost" value={`€${d.llm.cost_eur.toFixed(4)}`} />
              </div>

              <div>
                <h3 className="mb-1 text-xs font-semibold text-slate-400 uppercase">
                  Stages
                </h3>
                <ul>
                  {d.stages.map((s) => (
                    <StageRow key={s.name} stage={s} />
                  ))}
                </ul>
              </div>

              {d.errors.length > 0 && (
                <div>
                  <h3 className="mb-1 text-xs font-semibold text-red-500 uppercase">
                    Errors ({d.errors.length})
                  </h3>
                  <div className="space-y-1">
                    {d.errors.map((e, i) => (
                      <pre
                        key={i}
                        className="overflow-x-auto rounded-lg bg-red-50 p-2 text-[11px] whitespace-pre-wrap text-red-700"
                      >
                        {typeof e.message === "string"
                          ? `${e.pipeline ?? ""} ${e.scope ?? ""}\n${e.message}`
                          : JSON.stringify(e, null, 2)}
                      </pre>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function RunsPage() {
  const runs = useRuns();
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Runs</h1>
        <p className="text-sm text-slate-500">
          Every pipeline execution, with per-stage timings and what each one did.
        </p>
      </header>

      {runs.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : runs.error ? (
        <ErrorBox message="Could not load runs." />
      ) : (runs.data ?? []).length === 0 ? (
        <EmptyState icon={CalendarClock} title="No runs yet">
          The scheduler fires daily, or you can trigger one from <strong>Today</strong>.
        </EmptyState>
      ) : (
        <Card padded={false}>
          <ul className="divide-y divide-slate-100">
            {runs.data!.map((run) => (
              <li key={run.id}>
                <button
                  onClick={() => setOpenId(run.id)}
                  className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-slate-50"
                >
                  <StatusIcon status={run.status} />
                  <span className="w-12 shrink-0 text-sm font-medium">#{run.id}</span>
                  <span className="flex-1 text-sm text-slate-500">
                    {new Date(run.started_at).toLocaleString()}
                  </span>
                  <Badge tone="neutral">{run.trigger}</Badge>
                  {run.error_count > 0 && (
                    <Badge tone="warn">{run.error_count} errors</Badge>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <RunDetailDrawer runId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
