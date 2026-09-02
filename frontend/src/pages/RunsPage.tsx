import { useState } from "react";
import { useRunDetail, useRuns } from "@/api/hooks";
import { Card, ErrorBox, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";

function RunDetailDrawer({
  runId,
  onClose,
}: {
  runId: number | null;
  onClose: () => void;
}) {
  const detail = useRunDetail(runId);
  if (runId == null) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-xl overflow-y-auto bg-white p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="mb-4 text-sm text-slate-400 hover:text-slate-700" onClick={onClose}>
          ← Close
        </button>
        {detail.isLoading ? (
          <Spinner />
        ) : detail.error || !detail.data ? (
          <ErrorBox message="Could not load run" />
        ) : (
          <div className="space-y-4">
            <h2 className="text-lg font-bold">
              Run #{detail.data.run.id} · {detail.data.run.status}
            </h2>
            <p className="text-sm text-slate-500">
              LLM: {detail.data.llm.calls} calls · {detail.data.llm.cache_hits}{" "}
              cache hits · €{detail.data.llm.cost_eur.toFixed(4)}
            </p>

            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="pb-1">Stage</th>
                  <th className="pb-1">Status</th>
                  <th className="pb-1">Time</th>
                  <th className="pb-1">Stats</th>
                </tr>
              </thead>
              <tbody>
                {detail.data.stages.map((s) => (
                  <tr key={s.name} className="border-t border-slate-100 align-top">
                    <td className="py-1 font-medium">{s.name}</td>
                    <td
                      className={cn(
                        "py-1",
                        s.status === "ok"
                          ? "text-green-600"
                          : s.status === "skipped"
                            ? "text-slate-400"
                            : "text-amber-600",
                      )}
                    >
                      {s.status}
                    </td>
                    <td className="py-1 text-slate-500">{s.duration_s.toFixed(2)}s</td>
                    <td className="py-1 text-xs text-slate-500">
                      {Object.entries(s.stats)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" · ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {detail.data.errors.length > 0 && (
              <div className="space-y-1">
                {detail.data.errors.map((e, i) => (
                  <div key={i} className="rounded bg-red-50 p-2 text-xs text-red-700">
                    {JSON.stringify(e)}
                  </div>
                ))}
              </div>
            )}
          </div>
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
      <h1 className="text-2xl font-bold">Runs</h1>
      <Card>
        {runs.isLoading ? (
          <Spinner />
        ) : runs.error ? (
          <ErrorBox message="Could not load runs" />
        ) : runs.data && runs.data.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400">
                <th className="pb-2">#</th>
                <th className="pb-2">Trigger</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Started</th>
                <th className="pb-2">Errors</th>
              </tr>
            </thead>
            <tbody>
              {runs.data.map((run) => (
                <tr
                  key={run.id}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  onClick={() => setOpenId(run.id)}
                >
                  <td className="py-2">{run.id}</td>
                  <td className="py-2">{run.trigger}</td>
                  <td className="py-2">{run.status}</td>
                  <td className="py-2 text-slate-500">
                    {new Date(run.started_at).toLocaleString()}
                  </td>
                  <td className="py-2">{run.error_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-400">No runs yet.</p>
        )}
      </Card>
      <RunDetailDrawer runId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
