import { Check, SlidersHorizontal, ThumbsDown, ThumbsUp, TrendingDown, TrendingUp } from "lucide-react";
import { useApplyCalibration, useCalibration } from "@/api/hooks";
import { cn } from "@/lib/cn";
import { Badge, Button, Callout, Card, ErrorBox, Meter, Skeleton } from "./ui";

function corrTone(v: number): "good" | "bad" | "neutral" {
  if (v > 0.15) return "good";
  if (v < -0.15) return "bad";
  return "neutral";
}

export function CalibrationPanel() {
  const report = useCalibration();
  const apply = useApplyCalibration();
  const d = report.data;

  return (
    <Card title="Score calibration">
      <p className="-mt-2 mb-4 text-sm text-slate-500">
        Learns from the jobs you thumbed <ThumbsUp className="inline h-3.5 w-3.5" /> /{" "}
        <ThumbsDown className="inline h-3.5 w-3.5" /> in the job drawer and how far you
        took each one in the tracker, then proposes new component weights. Nothing
        changes until you apply it.
      </p>

      {report.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : report.error ? (
        <ErrorBox message="Could not load the calibration report." />
      ) : d ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge tone="neutral">{d.n_labeled} rated</Badge>
            <Badge tone={d.n_positive > 0 ? "good" : "neutral"}>
              {d.n_positive} positive
            </Badge>
            <Badge tone={d.n_negative > 0 ? "bad" : "neutral"}>
              {d.n_negative} negative
            </Badge>
          </div>

          {!d.ready ? (
            <Callout tone="info" icon={SlidersHorizontal}>
              {d.reason}
              <div className="mt-2">
                <Meter value={Math.min(1, d.n_labeled / d.min_labeled)} tone="info" />
                <span className="mt-1 block text-xs">
                  {d.n_labeled} / {d.min_labeled} needed
                </span>
              </div>
            </Callout>
          ) : (
            <>
              <div className="overflow-hidden rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Component</th>
                      <th className="px-3 py-2 text-right font-medium">Correlation</th>
                      <th className="px-3 py-2 text-right font-medium">Now</th>
                      <th className="px-3 py-2 text-right font-medium">Suggested</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {d.components.map((c) => {
                      const up = c.suggested_weight > c.current_weight;
                      const changed =
                        Math.abs(c.suggested_weight - c.current_weight) >= 0.05;
                      return (
                        <tr key={c.name}>
                          <td className="px-3 py-2 text-slate-700">{c.name}</td>
                          <td className="px-3 py-2 text-right">
                            <Badge tone={corrTone(c.correlation)}>
                              {c.correlation > 0 ? "+" : ""}
                              {c.correlation.toFixed(2)}
                            </Badge>
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                            {c.current_weight.toFixed(1)}
                          </td>
                          <td
                            className={cn(
                              "px-3 py-2 text-right font-medium tabular-nums",
                              changed
                                ? up
                                  ? "text-emerald-700"
                                  : "text-red-700"
                                : "text-slate-500",
                            )}
                          >
                            <span className="inline-flex items-center gap-1">
                              {changed &&
                                (up ? (
                                  <TrendingUp className="h-3.5 w-3.5" />
                                ) : (
                                  <TrendingDown className="h-3.5 w-3.5" />
                                ))}
                              {c.suggested_weight.toFixed(1)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <p className="text-xs text-slate-500">
                Rules / model blend: {d.current_blend_soft_ratio} →{" "}
                <span className="font-medium">{d.suggested_blend_soft_ratio}</span>
                {d.judge_correlation != null &&
                  ` (the model's own rating correlates ${d.judge_correlation.toFixed(2)})`}
              </p>

              <div className="flex items-center gap-3">
                <Button
                  icon={apply.isSuccess ? Check : SlidersHorizontal}
                  loading={apply.isPending}
                  onClick={() => apply.mutate()}
                >
                  {apply.isPending
                    ? "Applying…"
                    : apply.isSuccess
                      ? "Applied"
                      : "Apply suggested weights"}
                </Button>
                {apply.error && (
                  <span className="text-xs text-red-700">Could not apply.</span>
                )}
              </div>
            </>
          )}
        </div>
      ) : null}
    </Card>
  );
}
