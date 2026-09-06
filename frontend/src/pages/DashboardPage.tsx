import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlarmClock,
  AlertTriangle,
  Briefcase,
  Clock,
  Euro,
  ExternalLink,
  Filter,
  Loader2,
  MapPin,
  Play,
  Search,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  useCosts,
  useFollowUps,
  useJobs,
  useLatestRun,
  useRunDetail,
  useTriggerRun,
} from "@/api/hooks";
import type { JobCard as JobCardT } from "@/api/types";
import { JobDetailDrawer } from "@/components/JobDetailDrawer";
import {
  Badge,
  Callout,
  Chip,
  DECISION_TONE,
  EmptyState,
  ErrorBox,
  Input,
  ScoreRing,
  Skeleton,
  Stat,
  Button,
} from "@/components/ui";
import { cn } from "@/lib/cn";

const BUCKETS = [
  { key: "recommended", label: "Recommended" },
  { key: "maybe", label: "Maybe" },
  { key: "all", label: "All scored" },
] as const;

function daysAgo(iso: string | null): string | null {
  if (!iso) return null;
  const d = Math.floor((Date.now() - Date.parse(iso)) / 86_400_000);
  if (d <= 0) return "today";
  if (d === 1) return "yesterday";
  return `${d}d ago`;
}

/* ------------------------------------------------------------- live run bar */

function LiveRunBanner() {
  const latest = useLatestRun();
  const running = latest.data?.status === "running" ? latest.data.id : null;
  const detail = useRunDetail(running);

  if (!running) return null;
  const stages = detail.data?.stages ?? [];
  const done = stages.filter((s) => s.status !== "running").length;
  const current = stages.at(-1)?.name ?? "starting";

  return (
    <Callout tone="info" icon={Loader2}>
      <div className="flex flex-wrap items-center gap-x-2">
        <span className="font-medium">Run #{running} in progress</span>
        <span className="text-indigo-600">
          — {current} ({done}/10 stages)
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-indigo-100">
        <div
          className="h-full rounded-full bg-indigo-500 transition-[width] duration-700"
          style={{ width: `${(done / 10) * 100}%` }}
        />
      </div>
    </Callout>
  );
}

/* ---------------------------------------------------------------- job card */

function JobRow({ job, onOpen }: { job: JobCardT; onOpen: () => void }) {
  const posted = daysAgo(job.posted_at);
  return (
    <article
      onClick={onOpen}
      className="group cursor-pointer rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-slate-300 hover:shadow-sm"
    >
      <div className="flex items-start gap-4">
        <ScoreRing value={job.final_score} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-slate-900 group-hover:underline">
              {job.title}
            </h3>
            {job.is_new && (
              <Badge tone="info" title="First seen in the latest run">
                new
              </Badge>
            )}
            <Badge tone={DECISION_TONE[job.decision] ?? "neutral"}>{job.decision}</Badge>
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            <span className="font-medium text-slate-600">{job.company}</span>
            {job.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {job.is_remote ? "Remote" : job.location}
              </span>
            )}
            {job.weekly_hours != null && (
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {job.weekly_hours}h/wk
              </span>
            )}
            {job.salary && (
              <span className="inline-flex items-center gap-1">
                <Euro className="h-3.5 w-3.5" />
                {job.salary}
              </span>
            )}
            {posted && <span className="text-slate-400">{posted}</span>}
            <span className="text-slate-400">via {job.source}</span>
          </div>

          {/* why this score — the two halves of the blend, always visible */}
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1 text-slate-500">
              <TrendingUp className="h-3.5 w-3.5" />
              rules {Math.round(job.soft_score)}
            </span>
            {job.llm_holistic != null && (
              <span className="inline-flex items-center gap-1 text-slate-500">
                <Sparkles className="h-3.5 w-3.5" />
                model {Math.round(job.llm_holistic)}
              </span>
            )}
            {job.contract_type && (
              <span className="text-slate-400">{job.contract_type}</span>
            )}
          </div>

          {(job.strengths.length > 0 || job.missing.length > 0) && (
            <div className="mt-2 space-y-0.5 text-xs">
              {job.strengths.length > 0 && (
                <p className="text-emerald-700">
                  <span className="font-medium">Fits:</span> {job.strengths.join(" · ")}
                </p>
              )}
              {job.missing.length > 0 && (
                <p className="text-amber-700">
                  <span className="font-medium">Gap:</span> {job.missing[0]}
                </p>
              )}
            </div>
          )}
        </div>

        <a
          href={job.apply_url ?? job.url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="shrink-0 rounded-lg p-2 text-slate-300 transition-colors hover:bg-slate-100 hover:text-slate-600"
          title="Open the original posting"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
    </article>
  );
}

/* -------------------------------------------------------------------- page */

export function DashboardPage() {
  const costs = useCosts();
  const followUps = useFollowUps();
  const latestRun = useLatestRun();
  const trigger = useTriggerRun();

  const [bucket, setBucket] = useState<string>("recommended");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [contract, setContract] = useState("");
  const [maxAge, setMaxAge] = useState(0);
  const [hasSalary, setHasSalary] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);

  const jobs = useJobs({
    bucket,
    search: search.trim() || undefined,
    source: source || undefined,
  });
  const counts = jobs.data?.counts ?? {};
  const all = useMemo(() => jobs.data?.jobs ?? [], [jobs.data]);

  const sources = useMemo(
    () => [...new Set(all.map((j) => j.source))].sort(),
    [all],
  );
  const contracts = useMemo(
    () => [...new Set(all.map((j) => j.contract_type).filter(Boolean))].sort(),
    [all],
  );
  const list = useMemo(() => {
    const cutoff = maxAge ? Date.now() - maxAge * 86_400_000 : 0;
    return all.filter(
      (j) =>
        (!contract || j.contract_type === contract) &&
        (!hasSalary || !!j.salary) &&
        (!cutoff || (j.posted_at ? Date.parse(j.posted_at) >= cutoff : false)),
    );
  }, [all, contract, hasSalary, maxAge]);

  const running = latestRun.data?.status === "running";
  const newCount = all.filter((j) => j.is_new).length;
  const filtered = list.length !== all.length;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Today</h1>
          <p className="text-sm text-slate-500">
            Ranked by how well each posting fits your profile. You decide what to
            apply to.
          </p>
        </div>
        <Button
          icon={Play}
          loading={trigger.isPending || running}
          onClick={() => trigger.mutate(undefined)}
        >
          {running ? "Running…" : "Run pipeline now"}
        </Button>
      </header>

      <LiveRunBanner />

      {latestRun.data &&
        latestRun.data.status !== "running" &&
        latestRun.data.error_count > 0 && (
          <Callout tone="warn" icon={AlertTriangle}>
            <span className="font-medium">
              Run #{latestRun.data.id} finished with {latestRun.data.error_count}{" "}
              error{latestRun.data.error_count > 1 ? "s" : ""}.
            </span>{" "}
            Some sources or postings were skipped, so today's list may be short —{" "}
            <Link to="/runs" className="underline">
              see what failed
            </Link>
            .
          </Callout>
        )}

      {(followUps.data?.length ?? 0) > 0 && (
        <Callout tone="warn" icon={AlarmClock}>
          <span className="font-medium">
            {followUps.data!.length} follow-up
            {followUps.data!.length > 1 ? "s" : ""} due:
          </span>{" "}
          {followUps.data!.map((a) => a.job_title).join(", ")}
        </Callout>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Recommended"
          value={counts.recommended ?? 0}
          hint="worth your time today"
          icon={Sparkles}
          tone="good"
        />
        <Stat
          label="Maybe"
          value={counts.maybe ?? 0}
          hint="worth a skim"
          icon={Briefcase}
          tone="warn"
        />
        <Stat
          label="New this run"
          value={newCount}
          hint={latestRun.data ? `run #${latestRun.data.id}` : "no runs yet"}
          icon={TrendingUp}
        />
        <Stat
          label="LLM spend"
          value={costs.data ? `€${costs.data.cost_eur.toFixed(2)}` : "—"}
          hint={costs.data ? `of €${costs.data.budget_eur.toFixed(2)} this month` : undefined}
          icon={Euro}
        />
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {BUCKETS.map((b) => (
            <Chip
              key={b.key}
              active={bucket === b.key}
              onClick={() => setBucket(b.key)}
              count={b.key === "all" ? undefined : counts[b.key]}
            >
              {b.label}
            </Chip>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Search title or company…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-56 pl-8"
              />
            </div>
            <Button
              variant={showFilters || filtered ? "primary" : "secondary"}
              icon={Filter}
              onClick={() => setShowFilters((v) => !v)}
            >
              Filters
            </Button>
          </div>
        </div>

        {showFilters && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 text-sm">
            <select
              className="rounded-lg border border-slate-300 px-2 py-1.5"
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
              className="rounded-lg border border-slate-300 px-2 py-1.5"
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
              className="rounded-lg border border-slate-300 px-2 py-1.5"
              value={maxAge}
              onChange={(e) => setMaxAge(Number(e.target.value))}
            >
              <option value={0}>Any age</option>
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
            <label className="inline-flex items-center gap-1.5 text-slate-600">
              <input
                type="checkbox"
                checked={hasSalary}
                onChange={(e) => setHasSalary(e.target.checked)}
              />
              Has salary
            </label>
            {filtered && (
              <span className="ml-auto text-xs text-slate-400">
                {list.length} of {all.length}
              </span>
            )}
          </div>
        )}
      </div>

      {jobs.isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : jobs.error ? (
        <ErrorBox message="Could not load jobs." />
      ) : list.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={
            all.length === 0
              ? bucket === "recommended"
                ? "Nothing recommended yet"
                : "No scored jobs yet"
              : "Nothing matches those filters"
          }
          action={
            all.length === 0 ? (
              <Button icon={Play} loading={running} onClick={() => trigger.mutate(undefined)}>
                Run the pipeline
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() => {
                  setContract("");
                  setMaxAge(0);
                  setHasSalary(false);
                  setSource("");
                  setSearch("");
                }}
              >
                Clear filters
              </Button>
            )
          }
        >
          {all.length === 0 ? (
            bucket === "recommended" ? (
              <>
                Nothing cleared your “recommended” threshold in the last run. Check{" "}
                <button
                  className="underline"
                  onClick={() => setBucket("maybe")}
                >
                  Maybe
                </button>
                , or loosen the threshold in Settings.
              </>
            ) : (
              <>Run the pipeline to fetch and score today’s postings.</>
            )
          ) : null}
        </EmptyState>
      ) : (
        <div className={cn("space-y-2")}>
          {list.map((job) => (
            <JobRow key={job.id} job={job} onOpen={() => setOpenId(job.id)} />
          ))}
        </div>
      )}

      <JobDetailDrawer jobId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
