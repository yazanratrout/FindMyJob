import { useEffect, useState } from "react";
import { Activity, AlertTriangle, ArrowRight, Inbox } from "lucide-react";
import { useDigests, useMarkDigestsSeen } from "@/api/hooks";
import type { Digest } from "@/api/types";
import { JobDetailDrawer } from "@/components/JobDetailDrawer";
import {
  Badge,
  Card,
  Callout,
  EmptyState,
  ErrorBox,
  ScoreRing,
  Skeleton,
} from "@/components/ui";

function DigestCard({
  digest,
  onOpenJob,
}: {
  digest: Digest;
  onOpenJob: (id: number) => void;
}) {
  const s = digest.summary;
  const facts: [string, number, "good" | "warn" | "neutral"][] = [
    ["new", s.new_jobs, "neutral"],
    ["recommended", s.recommended, "good"],
    ["maybe", s.maybe, "warn"],
  ];

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold">Run #{digest.run_id}</span>
          <Badge tone={digest.run_status === "completed" ? "good" : "warn"}>
            {digest.run_status}
          </Badge>
          {!digest.seen && <Badge tone="info">new</Badge>}
        </div>
        <span className="text-xs text-slate-400">
          {new Date(digest.created_at).toLocaleString()}
        </span>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {facts.map(([label, value, tone]) => (
          <Badge key={label} tone={value > 0 ? tone : "neutral"}>
            {value} {label}
          </Badge>
        ))}
        {s.follow_ups_due > 0 && (
          <Badge tone="warn">{s.follow_ups_due} follow-ups due</Badge>
        )}
      </div>

      {digest.warnings.map((w, i) => (
        <div key={i} className="mb-2">
          <Callout tone="warn" icon={AlertTriangle}>
            {w}
          </Callout>
        </div>
      ))}

      {digest.items.length > 0 ? (
        <ul className="divide-y divide-slate-100">
          {digest.items.map((item) => (
            <li key={item.job_id}>
              <button
                onClick={() => onOpenJob(item.job_id)}
                className="group flex w-full items-center gap-3 py-2 text-left"
              >
                <ScoreRing value={item.final_score} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-800 group-hover:underline">
                    {item.title}
                  </span>
                  <span className="block truncate text-xs text-slate-500">
                    {item.company}
                  </span>
                </span>
                {item.is_new && <Badge tone="info">new</Badge>}
                <ArrowRight className="h-4 w-4 shrink-0 text-slate-300 group-hover:text-slate-600" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-400">
          Nothing cleared the recommend threshold in this run.
        </p>
      )}
    </Card>
  );
}

export function ActivityPage() {
  const digests = useDigests();
  const markSeen = useMarkDigestsSeen();
  const [openJob, setOpenJob] = useState<number | null>(null);

  useEffect(() => {
    if (digests.data?.some((d) => !d.seen)) markSeen.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [digests.data]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Activity</h1>
        <p className="text-sm text-slate-500">
          A digest per run — what it found and what it flagged. In-app only; nothing
          is e-mailed anywhere.
        </p>
      </header>

      {digests.isLoading ? (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : digests.error ? (
        <ErrorBox message="Could not load activity." />
      ) : (digests.data ?? []).length === 0 ? (
        <EmptyState icon={Inbox} title="No runs yet">
          Each pipeline run leaves a summary here — stats, new recommendations and any
          warnings.
        </EmptyState>
      ) : (
        <div className="space-y-4">
          {digests.data!.map((d) => (
            <DigestCard key={d.id} digest={d} onOpenJob={setOpenJob} />
          ))}
        </div>
      )}

      <JobDetailDrawer jobId={openJob} onClose={() => setOpenJob(null)} />
      <p className="flex items-center gap-1.5 text-xs text-slate-400">
        <Activity className="h-3.5 w-3.5" />
        Digests are kept per run; older jobs are pruned on the retention schedule.
      </p>
    </div>
  );
}
