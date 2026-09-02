import { useCosts, useHealth, useRuns, useTriggerRun } from "@/api/hooks";
import { Button, Card, ErrorBox, Spinner } from "@/components/ui";

export function DashboardPage() {
  const health = useHealth();
  const runs = useRuns();
  const costs = useCosts();
  const trigger = useTriggerRun();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Button onClick={() => trigger.mutate(undefined)} disabled={trigger.isPending}>
          {trigger.isPending ? "Starting…" : "Run pipeline now"}
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card title="Backend">
          {health.isLoading ? (
            <Spinner />
          ) : health.data ? (
            <p className="text-sm">
              {health.data.status} · v{health.data.version} · db{" "}
              {health.data.db_ok ? "ok" : "down"}
            </p>
          ) : (
            <ErrorBox message="unreachable" />
          )}
        </Card>
        <Card title="LLM spend (month)">
          {costs.data ? (
            <p className="text-sm">
              €{costs.data.cost_eur.toFixed(2)} / €{costs.data.budget_eur.toFixed(2)}
              <span className="block text-slate-400">
                projected €{costs.data.projected_month_end_eur.toFixed(2)}
              </span>
            </p>
          ) : (
            <Spinner />
          )}
        </Card>
        <Card title="Last run">
          {runs.data && runs.data.length > 0 ? (
            <p className="text-sm">
              #{runs.data[0].id} · {runs.data[0].status}
              <span className="block text-slate-400">
                {new Date(runs.data[0].started_at).toLocaleString()}
              </span>
            </p>
          ) : (
            <p className="text-sm text-slate-400">no runs yet</p>
          )}
        </Card>
      </div>

      <Card title="Recommended jobs">
        <p className="text-sm text-slate-500">
          The ranked job list arrives in CP17. For now, run the pipeline and check
          the Runs page.
        </p>
      </Card>
    </div>
  );
}
