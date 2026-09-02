import { useApplyCalibration, useCalibration } from "@/api/hooks";
import { cn } from "@/lib/cn";
import { Button, Card, ErrorBox, Spinner } from "./ui";

function corrColor(v: number): string {
  if (v > 0.15) return "text-green-700";
  if (v < -0.15) return "text-red-700";
  return "text-slate-400";
}

export function CalibrationPanel() {
  const report = useCalibration();
  const apply = useApplyCalibration();

  return (
    <Card title="Score calibration">
      <p className="mb-3 text-xs text-slate-500">
        Correlates each score component with the jobs you thumbed up / down and
        the ones you advanced in the tracker, then suggests new weights. Nothing
        changes until you apply it.
      </p>

      {report.isLoading ? (
        <Spinner />
      ) : report.error ? (
        <ErrorBox message="Could not load the calibration report" />
      ) : report.data ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            {report.data.n_labeled} rated job(s) — {report.data.n_positive} positive,{" "}
            {report.data.n_negative} negative.
          </p>

          {!report.data.ready ? (
            <p className="rounded bg-slate-50 p-2 text-xs text-slate-500">
              {report.data.reason}
            </p>
          ) : (
            <>
              <table className="w-full text-xs">
                <thead className="text-slate-400">
                  <tr>
                    <th className="py-1 text-left font-medium">component</th>
                    <th className="py-1 text-right font-medium">corr.</th>
                    <th className="py-1 text-right font-medium">weight</th>
                    <th className="py-1 text-right font-medium">suggested</th>
                  </tr>
                </thead>
                <tbody>
                  {report.data.components.map((c) => (
                    <tr key={c.name} className="border-t border-slate-100">
                      <td className="py-1">{c.name}</td>
                      <td className={cn("py-1 text-right tabular-nums", corrColor(c.correlation))}>
                        {c.correlation.toFixed(2)}
                      </td>
                      <td className="py-1 text-right text-slate-400 tabular-nums">
                        {c.current_weight.toFixed(1)}
                      </td>
                      <td className="py-1 text-right font-medium tabular-nums">
                        {c.suggested_weight.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <p className="text-xs text-slate-500">
                Soft / LLM blend: {report.data.current_blend_soft_ratio} →{" "}
                {report.data.suggested_blend_soft_ratio}
                {report.data.judge_correlation != null &&
                  ` (judge correlation ${report.data.judge_correlation.toFixed(2)})`}
              </p>

              <div className="flex items-center gap-3">
                <Button onClick={() => apply.mutate()} disabled={apply.isPending}>
                  {apply.isPending
                    ? "Applying…"
                    : apply.isSuccess
                      ? "Applied"
                      : "Apply suggested weights"}
                </Button>
                {apply.error && <span className="text-xs text-red-700">Could not apply</span>}
              </div>
            </>
          )}
        </div>
      ) : null}
    </Card>
  );
}
