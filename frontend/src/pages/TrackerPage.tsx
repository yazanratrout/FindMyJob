import { useState } from "react";
import { AlarmClock, ExternalLink, GripVertical, KanbanSquare } from "lucide-react";
import { useApplications, useUpdateApplication } from "@/api/hooks";
import type { Application, ApplicationStatus } from "@/api/types";
import { Badge, EmptyState, ErrorBox, Skeleton, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";

const COLUMNS: { status: ApplicationStatus; label: string; accent: string }[] = [
  { status: "interested", label: "Interested", accent: "bg-slate-400" },
  { status: "preparing", label: "Preparing", accent: "bg-indigo-400" },
  { status: "applied", label: "Applied", accent: "bg-blue-500" },
  { status: "interview", label: "Interview", accent: "bg-violet-500" },
  { status: "offer", label: "Offer", accent: "bg-emerald-500" },
  { status: "rejected", label: "Rejected", accent: "bg-red-400" },
  { status: "withdrawn", label: "Withdrawn", accent: "bg-slate-300" },
];

const DRAG_TYPE = "application/x-findmyjob-application";

function isOverdue(iso: string | null): boolean {
  return !!iso && Date.parse(iso) <= Date.now();
}

function AppCard({ app }: { app: Application }) {
  const update = useUpdateApplication();
  const [open, setOpen] = useState(false);

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData(DRAG_TYPE, String(app.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      className="group cursor-grab rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm transition-shadow active:cursor-grabbing hover:shadow-md"
    >
      <div className="flex items-start gap-1.5">
        <GripVertical className="mt-0.5 h-4 w-4 shrink-0 text-slate-300 group-hover:text-slate-400" />
        <div className="min-w-0 flex-1">
          <button
            onClick={() => setOpen((v) => !v)}
            className="block w-full text-left font-medium text-slate-800 hover:underline"
          >
            {app.job_title}
          </button>
          <div className="truncate text-xs text-slate-500">{app.company}</div>
        </div>
        <a
          href={app.apply_url ?? app.job_url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="shrink-0 text-slate-300 hover:text-slate-600"
          title="Open posting"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>

      {app.follow_up_at && !open && (
        <div className="mt-2 pl-5.5">
          <Badge tone={isOverdue(app.follow_up_at) ? "warn" : "neutral"}>
            <AlarmClock className="h-3 w-3" />
            {new Date(app.follow_up_at).toLocaleDateString()}
          </Badge>
        </div>
      )}

      {open && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          <label className="block text-xs text-slate-500">
            Status (or drag the card)
            <select
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1 text-xs"
              value={app.status}
              onChange={(e) =>
                update.mutate({
                  id: app.id,
                  patch: { status: e.target.value as ApplicationStatus },
                })
              }
            >
              {COLUMNS.map((c) => (
                <option key={c.status} value={c.status}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs text-slate-500">
            Follow up on
            <input
              type="date"
              className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1 text-xs"
              value={app.follow_up_at ? app.follow_up_at.slice(0, 10) : ""}
              onChange={(e) =>
                update.mutate({
                  id: app.id,
                  patch: {
                    follow_up_at: e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null,
                  },
                })
              }
            />
          </label>

          <Textarea
            className="h-16 text-xs"
            placeholder="Notes / outcome…"
            defaultValue={app.outcome_note}
            onBlur={(e) =>
              update.mutate({ id: app.id, patch: { outcome_note: e.target.value } })
            }
          />
        </div>
      )}
    </div>
  );
}

export function TrackerPage() {
  const apps = useApplications();
  const update = useUpdateApplication();
  const [dragOver, setDragOver] = useState<ApplicationStatus | null>(null);

  const drop = (status: ApplicationStatus) => (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(null);
    const id = Number(e.dataTransfer.getData(DRAG_TYPE));
    if (!id) return;
    const app = (apps.data ?? []).find((a) => a.id === id);
    if (!app || app.status === status) return;
    update.mutate({ id, patch: { status } });
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Tracker</h1>
        <p className="text-sm text-slate-500">
          Drag a card between columns to change its status. You submit every
          application yourself — nothing is sent from here.
        </p>
      </header>

      {apps.isLoading ? (
        <div className="flex gap-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 w-60" />
          ))}
        </div>
      ) : apps.error ? (
        <ErrorBox message="Could not load applications." />
      ) : (apps.data ?? []).length === 0 ? (
        <EmptyState icon={KanbanSquare} title="No applications yet">
          Open a job from <strong>Today</strong> and set its status — or generate a
          cover letter, which files it here automatically.
        </EmptyState>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {COLUMNS.map((col) => {
            const items = (apps.data ?? []).filter((a) => a.status === col.status);
            return (
              <div
                key={col.status}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(col.status);
                }}
                onDragLeave={() => setDragOver((s) => (s === col.status ? null : s))}
                onDrop={drop(col.status)}
                className={cn(
                  "w-60 shrink-0 rounded-xl p-2 transition-colors",
                  dragOver === col.status
                    ? "bg-indigo-50 ring-2 ring-indigo-300 ring-inset"
                    : "bg-slate-100/60",
                )}
              >
                <div className="mb-2 flex items-center gap-2 px-1 py-1">
                  <span className={cn("h-2 w-2 rounded-full", col.accent)} />
                  <span className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
                    {col.label}
                  </span>
                  <span className="ml-auto rounded-full bg-white px-1.5 text-xs text-slate-500">
                    {items.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {items.map((a) => (
                    <AppCard key={a.id} app={a} />
                  ))}
                  {items.length === 0 && (
                    <div className="rounded-lg border border-dashed border-slate-300 px-2 py-6 text-center text-xs text-slate-400">
                      drop here
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
