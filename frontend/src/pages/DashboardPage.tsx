import { useMemo, useState } from "react";
import {
  useCosts,
  useFollowUps,
  useHealth,
  useJobs,
  useRuns,
  useTriggerRun,
} from "@/api/hooks";
import type { JobCard as JobCardT } from "@/api/types";
import { JobDetailDrawer } from "@/components/JobDetailDrawer";
import { Button, Card, ErrorBox, Spinner } from "@/components/ui";
import { Input } from "@/components/ui";
import { cn } from "@/lib/cn";

const BUCKETS = [
  { key: "recommended", label: "Recommended" },
  { key: "maybe", label: "Maybe" },
  { key: "all", label: "All" },
];

function ScoreRing({ value }: { value: number }) {
  const color =
    value >= 70 ? "bg-green-600" : value >= 50 ? "bg-amber-500" : "bg-slate-400";
  return (
    <div
      className={cn(
        "flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white",
        color,
      )}
    >
      {Math.round(value)}
    </div>
  );
}

function JobRow({ job, onOpen }: { job: JobCardT; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="flex w-full items-start gap-3 rounded-lg border border-slate-200 bg-white p-4 text-left hover:border-slate-300"
    >
      <ScoreRing value={job.final_score} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold">{job.title}</span>
          {job.is_new && (
            <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
              NEW
            </span>
          )}
        </div>
        <div className="text-sm text-slate-500">
          {job.company}
          {job.location && ` · ${job.location}`}
          {job.weekly_hours && ` · ${job.weekly_hours}h/wk`}
          {job.salary && ` · ${job.salary}`}
          {` · ${job.source}`}
        </div>
        {job.strengths.length > 0 && (
          <div className="mt-1 text-xs text-green-700">
            + {job.strengths.join(" · ")}
          </div>
        )}
        {job.missing.length > 0 && (
          <div className="text-xs text-amber-700">− {job.missing[0]}</div>
        )}
      </div>
    </button>
  );
}

export function DashboardPage() {
  const health = useHealth();
  const runs = useRuns();
  const costs = useCosts();
  const followUps = useFollowUps();
  const trigger = useTriggerRun();

  const [bucket, setBucket] = useState("recommended");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [contract, setContract] = useState("");
  const [hasSalary, setHasSalary] = useState(false);
  const [maxAge, setMaxAge] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);

  const jobs = useJobs({
    bucket,
    search: search.trim() || undefined,
    source: source || undefined,
  });
  const counts = jobs.data?.counts ?? {};
  const allJobs = useMemo(() => jobs.data?.jobs ?? [], [jobs.data]);

  const sources = useMemo(
    () => [...new Set(allJobs.map((j) => j.source))].sort(),
    [allJobs],
  );
  const contracts = useMemo(
    () => [...new Set(allJobs.map((j) => j.contract_type).filter(Boolean))].sort(),
    [allJobs],
  );
  const list = useMemo(() => {
    const cutoff = maxAge ? Date.now() - maxAge * 86_400_000 : 0;
    return allJobs.filter(
      (j) =>
        (!contract || j.contract_type === contract) &&
        (!hasSalary || !!j.salary) &&
        (!cutoff || (j.posted_at ? Date.parse(j.posted_at) >= cutoff : false)),
    );
  }, [allJobs, contract, hasSalary, maxAge]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Button onClick={() => trigger.mutate(undefined)} disabled={trigger.isPending}>
          {trigger.isPending ? "Starting…" : "Run pipeline now"}
        </Button>
      </div>

      {(followUps.data?.length ?? 0) > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <span className="font-semibold">
            {followUps.data!.length} follow-up
            {followUps.data!.length > 1 ? "s" : ""} due:
          </span>{" "}
          {followUps.data!.map((a) => a.job_title).join(", ")}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card title="Backend">
          <p className="text-sm">
            {health.data
              ? `${health.data.status} · v${health.data.version}`
              : "…"}
          </p>
        </Card>
        <Card title="LLM spend (month)">
          <p className="text-sm">
            {costs.data
              ? `€${costs.data.cost_eur.toFixed(2)} / €${costs.data.budget_eur.toFixed(2)}`
              : "…"}
          </p>
        </Card>
        <Card title="Last run">
          <p className="text-sm">
            {runs.data?.[0]
              ? `#${runs.data[0].id} · ${runs.data[0].status}`
              : "no runs yet"}
          </p>
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {BUCKETS.map((b) => (
          <button
            key={b.key}
            onClick={() => setBucket(b.key)}
            className={cn(
              "rounded-full px-3 py-1 text-sm font-medium",
              bucket === b.key
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600",
            )}
          >
            {b.label}
            {counts[b.key === "all" ? "recommended" : b.key] != null &&
              b.key !== "all" &&
              ` (${counts[b.key] ?? 0})`}
          </button>
        ))}
        <Input
          placeholder="Search title / company…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-auto max-w-xs"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select
          className="rounded border border-slate-300 px-2 py-1"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-slate-300 px-2 py-1"
          value={contract}
          onChange={(e) => setContract(e.target.value)}
        >
          <option value="">Any contract</option>
          {contracts.map((c) => (
            <option key={c} value={c ?? ""}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-slate-300 px-2 py-1"
          value={maxAge}
          onChange={(e) => setMaxAge(Number(e.target.value))}
        >
          <option value={0}>Any age</option>
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
        </select>
        <label className="flex items-center gap-1 text-slate-600">
          <input
            type="checkbox"
            checked={hasSalary}
            onChange={(e) => setHasSalary(e.target.checked)}
          />
          Has salary
        </label>
        {list.length !== allJobs.length && (
          <span className="text-slate-400">
            {list.length} of {allJobs.length}
          </span>
        )}
      </div>

      {jobs.isLoading ? (
        <Spinner />
      ) : jobs.error ? (
        <ErrorBox message="Could not load jobs" />
      ) : list.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">
            Nothing here yet. Run the pipeline, then check back.
          </p>
        </Card>
      ) : (
        <div className="space-y-2">
          {list.map((job) => (
            <JobRow key={job.id} job={job} onOpen={() => setOpenId(job.id)} />
          ))}
        </div>
      )}

      <JobDetailDrawer jobId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
