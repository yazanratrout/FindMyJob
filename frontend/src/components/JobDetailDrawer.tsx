import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Circle,
  ExternalLink,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import {
  useClearJobFeedback,
  useCreateApplication,
  useJobDetail,
  useSetJobFeedback,
  useUpdateApplication,
} from "@/api/hooks";
import type {
  ApplicationStatus,
  DocumentNeed,
  FeedbackVerdict,
  ScoreComponent,
} from "@/api/types";
import { cn } from "@/lib/cn";
import { CoverLetterPanel } from "./CoverLetterPanel";
import {
  Badge,
  Callout,
  DECISION_TONE,
  ErrorBox,
  Meter,
  ScoreRing,
  Spinner,
  Tabs,
} from "./ui";

const STATUSES: ApplicationStatus[] = [
  "interested",
  "preparing",
  "applied",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

type TabKey = "overview" | "analysis" | "documents" | "letter" | "posting";

/* --------------------------------------------------------------- controls */

function StatusControl({
  jobId,
  applicationId,
  status,
}: {
  jobId: number;
  applicationId: number | null;
  status: ApplicationStatus | null;
}) {
  const create = useCreateApplication();
  const update = useUpdateApplication();

  const change = async (next: ApplicationStatus) => {
    let id = applicationId;
    if (id == null) id = (await create.mutateAsync(jobId)).id;
    update.mutate({ id, patch: { status: next } });
  };

  return (
    <label className="inline-flex items-center gap-1.5 text-sm text-slate-500">
      Status
      <select
        className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-800"
        value={status ?? "interested"}
        onChange={(e) => change(e.target.value as ApplicationStatus)}
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}

function FeedbackControl({
  jobId,
  current,
}: {
  jobId: number;
  current: FeedbackVerdict | null;
}) {
  const set = useSetJobFeedback(jobId);
  const clear = useClearJobFeedback(jobId);
  const busy = set.isPending || clear.isPending;

  const click = (verdict: FeedbackVerdict) =>
    current === verdict ? clear.mutate() : set.mutate(verdict);

  return (
    <span
      className="inline-flex items-center gap-1"
      title="Teaches the scorer what you actually want — see Settings → Score calibration"
    >
      {(
        [
          ["up", ThumbsUp, "hover:text-emerald-600"],
          ["down", ThumbsDown, "hover:text-red-600"],
        ] as const
      ).map(([v, Icon, hover]) => (
        <button
          key={v}
          disabled={busy}
          onClick={() => click(v)}
          aria-label={v === "up" ? "Good recommendation" : "Bad recommendation"}
          className={cn(
            "rounded-lg border p-2 transition-colors disabled:opacity-40",
            current === v
              ? "border-slate-900 bg-slate-900 text-white"
              : cn("border-slate-300 text-slate-400", hover),
          )}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </span>
  );
}

/* ----------------------------------------------------------- score section */

const COMPONENT_LABELS: Record<string, string> = {
  skills_match: "Skills match",
  field_relevance: "Field relevance",
  language_fit: "Language fit",
  hours_fit: "Hours fit",
  seniority_fit: "Seniority fit",
  recency: "Freshness",
  salary_fit: "Salary info",
  company_affinity: "Company affinity",
};

function Breakdown({ breakdown }: { breakdown: Record<string, ScoreComponent> }) {
  const rows = Object.entries(breakdown).sort(
    (a, b) => b[1].contribution - a[1].contribution,
  );
  return (
    <div className="space-y-2">
      {rows.map(([key, c]) => (
        <div key={key} className="flex items-center gap-3 text-xs">
          <span className="w-32 shrink-0 text-slate-500">
            {COMPONENT_LABELS[key] ?? key}
          </span>
          <Meter
            value={c.raw}
            tone={c.raw >= 0.7 ? "good" : c.raw >= 0.4 ? "warn" : "bad"}
          />
          <span className="w-24 shrink-0 text-right tabular-nums text-slate-400">
            {Math.round(c.raw * 100)}% × {c.weight}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- analysis tab */

interface Analysis {
  must_haves?: string[];
  nice_haves?: string[];
  skills?: { name: string; required?: boolean }[];
  languages?: { lang: string; cefr?: string | null; required?: boolean }[];
  weekly_hours?: number | null;
  weekly_hours_basis?: string;
  contract_type?: string;
  start_date_text?: string | null;
  deadline?: string | null;
  application_method?: string;
  enrollment_required?: string;
  red_flags?: string[];
  source_snippets?: Record<string, string>;
}

function Fact({
  label,
  value,
  snippet,
}: {
  label: string;
  value: string;
  snippet?: string;
}) {
  return (
    <div className="flex gap-3 py-1" title={snippet}>
      <dt className="w-32 shrink-0 text-slate-400">{label}</dt>
      <dd
        className={cn(
          "text-slate-700",
          snippet && "cursor-help border-b border-dotted border-slate-300",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function ChipList({ items, className }: { items: string[]; className: string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((t) => (
        <span key={t} className={cn("rounded-md px-2 py-1 text-xs", className)}>
          {t}
        </span>
      ))}
    </div>
  );
}

function AnalysisTab({ analysis }: { analysis: Analysis }) {
  const s = analysis.source_snippets ?? {};
  const sections: [string, string[] | undefined, string][] = [
    ["Must have", analysis.must_haves, "bg-amber-50 text-amber-800"],
    ["Nice to have", analysis.nice_haves, "bg-slate-100 text-slate-600"],
    ["Red flags", analysis.red_flags, "bg-red-50 text-red-700"],
  ];

  return (
    <div className="space-y-5">
      <dl className="text-sm">
        {analysis.weekly_hours != null && (
          <Fact
            label="Weekly hours"
            value={`${analysis.weekly_hours}h (${analysis.weekly_hours_basis ?? "unknown"})`}
            snippet={s.weekly_hours}
          />
        )}
        {analysis.contract_type && (
          <Fact label="Contract" value={analysis.contract_type} snippet={s.contract_type} />
        )}
        {analysis.enrollment_required && analysis.enrollment_required !== "unknown" && (
          <Fact
            label="Enrolment"
            value={analysis.enrollment_required}
            snippet={s.enrollment_required}
          />
        )}
        {analysis.start_date_text && (
          <Fact label="Start" value={analysis.start_date_text} snippet={s.start_date_text} />
        )}
        {analysis.deadline && (
          <Fact label="Deadline" value={analysis.deadline} snippet={s.deadline} />
        )}
        {analysis.application_method && analysis.application_method !== "unknown" && (
          <Fact label="Apply via" value={analysis.application_method} />
        )}
      </dl>

      {(analysis.languages ?? []).length > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs font-semibold text-slate-400 uppercase">
            Languages
          </h4>
          <div className="flex flex-wrap gap-1.5" title={s.languages}>
            {analysis.languages!.map((l) => (
              <Badge key={l.lang} tone={l.required === false ? "neutral" : "info"}>
                {l.lang}
                {l.cefr ? ` ${l.cefr}` : ""}
                {l.required === false ? " (nice)" : ""}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {(analysis.skills ?? []).length > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs font-semibold text-slate-400 uppercase">Skills</h4>
          <div className="flex flex-wrap gap-1.5">
            {analysis.skills!.map((sk) => (
              <span
                key={sk.name}
                className={cn(
                  "rounded-md px-2 py-1 text-xs",
                  sk.required
                    ? "bg-slate-800 text-white"
                    : "bg-slate-100 text-slate-600",
                )}
                title={sk.required ? "Required" : "Nice to have"}
              >
                {sk.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {sections.map(([label, items, style]) =>
        (items ?? []).length > 0 ? (
          <div key={label}>
            <h4 className="mb-1.5 text-xs font-semibold text-slate-400 uppercase">
              {label}
            </h4>
            <ChipList items={items!} className={style} />
          </div>
        ) : null,
      )}

      <p className="text-xs text-slate-400">
        Extracted by the analyser from the posting. Hover an underlined value to see
        the sentence it came from.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ drawer */

const NECESSITY_TONE: Record<DocumentNeed["necessity"], "bad" | "warn" | "neutral"> = {
  required: "bad",
  likely: "warn",
  optional: "neutral",
};

export function JobDetailDrawer({
  jobId,
  onClose,
}: {
  jobId: number | null;
  onClose: () => void;
}) {
  const detail = useJobDetail(jobId);
  const [tab, setTab] = useState<TabKey>("overview");

  useEffect(() => setTab("overview"), [jobId]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (jobId == null) return null;
  const d = detail.data;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-slate-900/30 backdrop-blur-[1px]"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {detail.isLoading ? (
          <Spinner />
        ) : detail.error || !d ? (
          <div className="p-6">
            <ErrorBox message="Could not load this job." />
          </div>
        ) : (
          <>
            {/* sticky header */}
            <header className="border-b border-slate-200 p-6 pb-4">
              <div className="mb-3 flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-4">
                  <ScoreRing value={d.final_score} size="lg" />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-xl font-bold text-slate-900">{d.title}</h2>
                      <Badge tone={DECISION_TONE[d.decision] ?? "neutral"}>
                        {d.decision}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-sm text-slate-500">
                      {d.company}
                      {d.location && ` · ${d.is_remote ? "Remote" : d.location}`}
                      {d.weekly_hours != null && ` · ${d.weekly_hours}h/wk`}
                      {d.salary && ` · ${d.salary}`}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      rules {Math.round(d.soft_score)}
                      {d.llm_holistic != null &&
                        ` · model ${Math.round(d.llm_holistic)}`}{" "}
                      · via {d.source}
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  aria-label="Close"
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <a href={d.apply_url ?? d.url} target="_blank" rel="noreferrer">
                  <span className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700">
                    <ExternalLink className="h-4 w-4" />
                    Open posting
                  </span>
                </a>
                <StatusControl
                  jobId={d.id}
                  applicationId={d.application_id}
                  status={d.application_status}
                />
                <FeedbackControl jobId={d.id} current={d.feedback} />
              </div>
            </header>

            <Tabs
              className="px-6"
              active={tab}
              onChange={setTab}
              tabs={[
                { key: "overview", label: "Overview" },
                { key: "analysis", label: "Analysis" },
                {
                  key: "documents",
                  label: "Documents",
                  count: d.documents_needed.length || undefined,
                },
                { key: "letter", label: "Cover letter" },
                { key: "posting", label: "Posting" },
              ]}
            />

            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              {tab === "overview" && (
                <div className="space-y-5">
                  {!d.hard_pass && (
                    <Callout tone="bad" icon={AlertTriangle}>
                      <span className="font-medium">Hard-filtered:</span>{" "}
                      {d.hard_failures.join(", ")} — it breaks a limit you marked as
                      strict in Settings.
                    </Callout>
                  )}

                  {d.rationale && (
                    <div>
                      <h3 className="mb-1.5 text-xs font-semibold text-slate-400 uppercase">
                        Assessment
                      </h3>
                      <p className="text-sm text-slate-700">{d.rationale}</p>
                    </div>
                  )}

                  {(d.strengths.length > 0 || d.missing.length > 0) && (
                    <div className="grid gap-4 sm:grid-cols-2">
                      {d.strengths.length > 0 && (
                        <div>
                          <h3 className="mb-1.5 text-xs font-semibold text-emerald-600 uppercase">
                            Lead with
                          </h3>
                          <ul className="space-y-1 text-sm text-slate-700">
                            {d.strengths.map((x) => (
                              <li key={x}>· {x}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {d.missing.length > 0 && (
                        <div>
                          <h3 className="mb-1.5 text-xs font-semibold text-amber-600 uppercase">
                            Gaps
                          </h3>
                          <ul className="space-y-1 text-sm text-slate-700">
                            {d.missing.map((x) => (
                              <li key={x}>· {x}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  <div>
                    <h3 className="mb-2 text-xs font-semibold text-slate-400 uppercase">
                      Why this score
                    </h3>
                    <Breakdown breakdown={d.soft_breakdown} />
                    <p className="mt-2 text-xs text-slate-400">
                      Each component is 0–100% of its weight. The final score blends
                      this rules score with the model’s holistic rating.
                    </p>
                  </div>
                </div>
              )}

              {tab === "analysis" &&
                (d.analysis ? (
                  <AnalysisTab analysis={d.analysis as Analysis} />
                ) : (
                  <p className="text-sm text-slate-500">
                    No analysis yet — this job hasn’t been through the analyser.
                  </p>
                ))}

              {tab === "documents" && (
                <ul className="space-y-2">
                  {d.documents_needed.map((doc) => (
                    <li
                      key={doc.doc_type}
                      className="flex items-start gap-3 rounded-lg border border-slate-200 p-3"
                    >
                      {doc.have ? (
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                      ) : (
                        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium capitalize">
                            {doc.doc_type.replace("_", " ")}
                          </span>
                          <Badge tone={NECESSITY_TONE[doc.necessity]}>
                            {doc.necessity}
                          </Badge>
                          {!doc.have && (
                            <span className="text-xs text-slate-400">
                              not uploaded
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 text-xs text-slate-500">{doc.reason}</p>
                      </div>
                    </li>
                  ))}
                  {d.documents_needed.length === 0 && (
                    <p className="text-sm text-slate-500">
                      No document checklist yet — run the pipeline to build one.
                    </p>
                  )}
                </ul>
              )}

              {tab === "letter" && (
                <div className="space-y-3">
                  <Callout tone="warn">
                    Every claim is traced back to your profile — review them before you
                    send anything. Nothing is submitted for you.
                  </Callout>
                  <CoverLetterPanel jobId={d.id} />
                </div>
              )}

              {tab === "posting" && (
                <pre className="rounded-lg bg-slate-50 p-4 text-xs leading-relaxed whitespace-pre-wrap text-slate-700">
                  {d.jd_text ?? "No description text was captured for this posting."}
                </pre>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
