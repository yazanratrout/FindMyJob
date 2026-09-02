import { useRuns } from "@/api/hooks";
import { Card, ErrorBox, Spinner } from "@/components/ui";

export function RunsPage() {
  const runs = useRuns();

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
                <tr key={run.id} className="border-t border-slate-100">
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
    </div>
  );
}
