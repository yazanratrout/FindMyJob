import { useApplications, useUpdateApplication } from "@/api/hooks";
import type { Application, ApplicationStatus } from "@/api/types";
import { Card, ErrorBox, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";

const COLUMNS: { status: ApplicationStatus; label: string }[] = [
  { status: "interested", label: "Interested" },
  { status: "preparing", label: "Preparing" },
  { status: "applied", label: "Applied" },
  { status: "interview", label: "Interview" },
  { status: "offer", label: "Offer" },
  { status: "rejected", label: "Rejected" },
  { status: "withdrawn", label: "Withdrawn" },
];

function AppCard({ app }: { app: Application }) {
  const update = useUpdateApplication();
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3 text-sm">
      <a
        href={app.apply_url ?? app.job_url}
        target="_blank"
        rel="noreferrer"
        className="font-medium hover:underline"
      >
        {app.job_title}
      </a>
      <div className="text-xs text-slate-500">{app.company}</div>

      <select
        className="mt-2 w-full rounded border border-slate-300 px-1 py-1 text-xs"
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

      <label className="mt-2 block text-xs text-slate-500">
        Follow up
        <input
          type="date"
          className="mt-0.5 w-full rounded border border-slate-300 px-1 py-0.5 text-xs"
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

      <textarea
        className="mt-2 h-14 w-full rounded border border-slate-300 p-1 text-xs"
        placeholder="Notes / outcome…"
        defaultValue={app.outcome_note}
        onBlur={(e) =>
          update.mutate({ id: app.id, patch: { outcome_note: e.target.value } })
        }
      />
    </div>
  );
}

export function TrackerPage() {
  const apps = useApplications();

  if (apps.isLoading) return <Spinner />;
  if (apps.error) return <ErrorBox message="Could not load applications" />;

  const byStatus = (status: ApplicationStatus) =>
    (apps.data ?? []).filter((a) => a.status === status);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Tracker</h1>
      {(apps.data ?? []).length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">
            No applications yet. Generating a cover letter for a job adds it here.
          </p>
        </Card>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {COLUMNS.map((col) => {
            const items = byStatus(col.status);
            return (
              <div key={col.status} className="w-56 shrink-0">
                <div
                  className={cn(
                    "mb-2 flex items-center justify-between text-xs font-semibold text-slate-500 uppercase",
                  )}
                >
                  {col.label}
                  <span className="rounded bg-slate-100 px-1.5">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.map((a) => (
                    <AppCard key={a.id} app={a} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
