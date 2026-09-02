import { useState } from "react";
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
import { Button, ErrorBox, Spinner } from "./ui";

const STATUSES: ApplicationStatus[] = [
  "interested",
  "preparing",
  "applied",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

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
    if (id == null) {
      const app = await create.mutateAsync(jobId);
      id = app.id;
    }
    update.mutate({ id, patch: { status: next } });
  };

  return (
    <label className="text-sm text-slate-600">
      Status:{" "}
      <select
        className="rounded border border-slate-300 px-2 py-1 text-sm"
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

  const click = (verdict: FeedbackVerdict) => {
    if (current === verdict) clear.mutate();
    else set.mutate(verdict);
  };

  return (
    <span className="inline-flex items-center gap-1" title="Teach the scorer what you like">
      {(["up", "down"] as FeedbackVerdict[]).map((v) => (
        <button
          key={v}
          disabled={busy}
          onClick={() => click(v)}
          className={cn(
            "rounded border px-2 py-1 text-sm transition-colors disabled:opacity-40",
            current === v
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-300 text-slate-500 hover:bg-slate-100",
          )}
        >
          {v === "up" ? "👍" : "👎"}
        </button>
      ))}
    </span>
  );
}

function Bar({ name, c }: { name: string; c: ScoreComponent }) {
  const pct = Math.round(c.raw * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-32 shrink-0 text-slate-500">{name}</span>
      <div className="h-2 flex-1 rounded bg-slate-100">
        <div className="h-2 rounded bg-slate-700" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-14 shrink-0 text-right text-slate-400">
        {pct}% ×{c.weight}
      </span>
    </div>
  );
}

const NECESSITY_COLOR: Record<DocumentNeed["necessity"], string> = {
  required: "text-red-600",
  likely: "text-amber-600",
  optional: "text-slate-400",
};

export function JobDetailDrawer({
  jobId,
  onClose,
}: {
  jobId: number | null;
  onClose: () => void;
}) {
  const detail = useJobDetail(jobId);
  const [showCoverLetter, setShowCoverLetter] = useState(false);

  if (jobId == null) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-2xl overflow-y-auto bg-white p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <button className="text-sm text-slate-400 hover:text-slate-700" onClick={onClose}>
            ← Close
          </button>
        </div>

        {detail.isLoading ? (
          <Spinner />
        ) : detail.error ? (
          <ErrorBox message="Could not load this job" />
        ) : detail.data ? (
          (() => {
            const d = detail.data;
            return (
              <div className="space-y-5">
                <div>
                  <h2 className="text-xl font-bold">{d.title}</h2>
                  <p className="text-sm text-slate-500">
                    {d.company}
                    {d.location && ` · ${d.location}`}
                    {d.weekly_hours && ` · ${d.weekly_hours}h/wk`}
                    {d.salary && ` · ${d.salary}`}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <a href={d.apply_url ?? d.url} target="_blank" rel="noreferrer">
                      <Button>Open posting ↗</Button>
                    </a>
                    <Button
                      variant={showCoverLetter ? "ghost" : "primary"}
                      onClick={() => setShowCoverLetter((v) => !v)}
                    >
                      {showCoverLetter ? "Hide cover letter" : "Prepare cover letter"}
                    </Button>
                    <StatusControl
                      jobId={d.id}
                      applicationId={d.application_id}
                      status={d.application_status}
                    />
                    <FeedbackControl jobId={d.id} current={d.feedback} />
                  </div>
                </div>

                {showCoverLetter && jobId != null && (
                  <section className="rounded-md border border-slate-200 bg-slate-50 p-3">
                    <h3 className="mb-2 text-sm font-semibold text-slate-500 uppercase">
                      Cover letter
                    </h3>
                    <p className="mb-2 text-xs text-slate-500">
                      Review every claim against your profile before you send this.
                    </p>
                    <CoverLetterPanel jobId={jobId} />
                  </section>
                )}

                <section>
                  <h3 className="mb-2 text-sm font-semibold text-slate-500 uppercase">
                    Match — {Math.round(d.final_score)}
                    <span className="ml-2 font-normal text-slate-400">
                      soft {Math.round(d.soft_score)}
                      {d.llm_holistic != null && ` · llm ${Math.round(d.llm_holistic)}`} ·{" "}
                      {d.decision}
                    </span>
                  </h3>
                  {!d.hard_pass && (
                    <div className="mb-2 rounded bg-red-50 p-2 text-xs text-red-700">
                      Hard-filtered: {d.hard_failures.join(", ")}
                    </div>
                  )}
                  <div className="space-y-1">
                    {Object.entries(d.soft_breakdown).map(([k, c]) => (
                      <Bar key={k} name={k} c={c} />
                    ))}
                  </div>
                </section>

                {d.rationale && (
                  <section>
                    <h3 className="mb-1 text-sm font-semibold text-slate-500 uppercase">
                      Assessment
                    </h3>
                    <p className="text-sm">{d.rationale}</p>
                    {d.strengths.length > 0 && (
                      <p className="mt-1 text-xs text-green-700">
                        Highlight: {d.strengths.join(" · ")}
                      </p>
                    )}
                    {d.missing.length > 0 && (
                      <p className="text-xs text-amber-700">
                        Missing: {d.missing.join(" · ")}
                      </p>
                    )}
                  </section>
                )}

                <section>
                  <h3 className="mb-1 text-sm font-semibold text-slate-500 uppercase">
                    Documents
                  </h3>
                  <ul className="text-sm">
                    {d.documents_needed.map((doc) => (
                      <li key={doc.doc_type} className="flex items-center gap-2">
                        <span className={cn("w-3", doc.have ? "text-green-600" : "text-slate-300")}>
                          {doc.have ? "✓" : "○"}
                        </span>
                        <span className="w-28 capitalize">{doc.doc_type.replace("_", " ")}</span>
                        <span className={cn("w-16 text-xs", NECESSITY_COLOR[doc.necessity])}>
                          {doc.necessity}
                        </span>
                        <span className="text-xs text-slate-400">{doc.reason}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                {d.jd_text && (
                  <section>
                    <h3 className="mb-1 text-sm font-semibold text-slate-500 uppercase">
                      Original posting
                    </h3>
                    <pre className="max-h-96 overflow-y-auto rounded bg-slate-50 p-3 text-xs whitespace-pre-wrap">
                      {d.jd_text}
                    </pre>
                  </section>
                )}
              </div>
            );
          })()
        ) : null}
      </div>
    </div>
  );
}
