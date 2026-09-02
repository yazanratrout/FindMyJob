import { useEffect, useState } from "react";
import { useDigests, useMarkDigestsSeen } from "@/api/hooks";
import type { Digest } from "@/api/types";
import { JobDetailDrawer } from "@/components/JobDetailDrawer";
import { Card, ErrorBox, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";

function DigestCard({
  digest,
  onOpenJob,
}: {
  digest: Digest;
  onOpenJob: (id: number) => void;
}) {
  const s = digest.summary;
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <span className="font-semibold">Run #{digest.run_id}</span>
          <span
            className={cn(
              "ml-2 rounded px-1.5 py-0.5 text-xs",
              digest.run_status === "completed"
                ? "bg-green-100 text-green-700"
                : "bg-amber-100 text-amber-700",
            )}
          >
            {digest.run_status}
          </span>
          {!digest.seen && (
            <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
              new
            </span>
          )}
        </div>
        <span className="text-xs text-slate-400">
          {new Date(digest.created_at).toLocaleString()}
        </span>
      </div>

      <p className="mt-1 text-sm text-slate-600">
        {s.new_jobs} new job{s.new_jobs === 1 ? "" : "s"} · {s.recommended}{" "}
        recommended · {s.maybe} maybe
        {s.follow_ups_due > 0 && ` · ${s.follow_ups_due} follow-up(s) due`}
      </p>

      {digest.warnings.map((w, i) => (
        <div
          key={i}
          className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800"
        >
          {w}
        </div>
      ))}

      {digest.items.length > 0 && (
        <ul className="mt-3 space-y-1">
          {digest.items.map((item) => (
            <li key={item.job_id}>
              <button
                className="text-left text-sm hover:underline"
                onClick={() => onOpenJob(item.job_id)}
              >
                <span className="font-medium">
                  {Math.round(item.final_score)}
                </span>{" "}
                {item.title} · {item.company}
                {item.is_new && (
                  <span className="ml-1 text-[10px] font-semibold text-blue-600">
                    NEW
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
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
      <h1 className="text-2xl font-bold">Activity</h1>
      {digests.isLoading ? (
        <Spinner />
      ) : digests.error ? (
        <ErrorBox message="Could not load activity" />
      ) : (digests.data ?? []).length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">
            No runs yet. Each pipeline run produces a summary here.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {digests.data!.map((d) => (
            <DigestCard key={d.id} digest={d} onOpenJob={setOpenJob} />
          ))}
        </div>
      )}
      <JobDetailDrawer jobId={openJob} onClose={() => setOpenJob(null)} />
    </div>
  );
}
