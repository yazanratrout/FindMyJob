import { type ChangeEvent, type ReactNode, useMemo, useState } from "react";
import { ApiError } from "@/api/client";
import {
  useAddTerm,
  useDeleteDocument,
  useDeleteTerm,
  useDocuments,
  useParseProfile,
  useProfile,
  useSemesterTerms,
  useSuggestKeywords,
  useUpdateProfile,
  useUploadDocument,
} from "@/api/hooks";
import type { DocumentType, Settings, SettingsUpdate } from "@/api/types";
import { ChipToggle, Checkbox, Field, Select, TagInput } from "@/components/form";
import { Button, Card, ErrorBox, Spinner } from "@/components/ui";

export interface StepProps {
  draft: SettingsUpdate;
  set: <K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) => void;
}

const JOB_TYPES = [
  { value: "werkstudent", label: "Werkstudent" },
  { value: "student_assistant", label: "Student assistant" },
  { value: "praktikum", label: "Praktikum / internship" },
  { value: "thesis", label: "Thesis" },
  { value: "minijob", label: "Minijob" },
];
const CONTRACT_TYPES = [
  { value: "werkstudent", label: "Werkstudent" },
  { value: "part_time", label: "Part-time" },
  { value: "minijob", label: "Minijob" },
  { value: "praktikum", label: "Praktikum" },
  { value: "full_time", label: "Full-time" },
];
const CEFR = ["A1", "A2", "B1", "B2", "C1", "C2", "native"];
const DOC_TYPES: { value: DocumentType; label: string }[] = [
  { value: "cv", label: "CV" },
  { value: "enrollment", label: "Enrolment certificate" },
  { value: "transcript", label: "Transcript / Notenspiegel" },
  { value: "reference", label: "Reference letter" },
];
const WEIGHT_KEYS = [
  "skills_match",
  "field_relevance",
  "language_fit",
  "hours_fit",
  "seniority_fit",
  "recency",
  "salary_fit",
  "company_affinity",
];

// --------------------------------------------------------------- Documents
export function DocumentsStep() {
  const docs = useDocuments();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();
  const [type, setType] = useState<DocumentType>("cv");

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload.mutate({ type, file });
    e.target.value = "";
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Upload your CV (required) and any supporting documents. They stay on this
        machine.
      </p>
      <div className="flex items-end gap-2">
        <Field label="Document type">
          <Select value={type} onChange={(e) => setType(e.target.value as DocumentType)}>
            {DOC_TYPES.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </Select>
        </Field>
        <label className="cursor-pointer rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700">
          {upload.isPending ? "Uploading…" : "Choose file"}
          <input
            type="file"
            className="hidden"
            accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
            onChange={onFile}
          />
        </label>
      </div>
      {upload.error instanceof ApiError && <ErrorBox message={upload.error.message} />}

      {docs.isLoading ? (
        <Spinner />
      ) : (
        <ul className="divide-y divide-slate-100 rounded-md border border-slate-200">
          {(docs.data ?? []).map((d) => (
            <li key={d.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{d.type}</span> · {d.filename}
                <span className="text-slate-400">
                  {" "}
                  · {d.parse_status}
                  {d.text_chars > 0 && ` · ${d.text_chars} chars`}
                </span>
              </span>
              <Button variant="ghost" onClick={() => remove.mutate(d.id)}>
                Delete
              </Button>
            </li>
          ))}
          {docs.data?.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-400">No documents yet.</li>
          )}
        </ul>
      )}
    </div>
  );
}

// ----------------------------------------------------------------- Profile
export function ProfileStep() {
  const profile = useProfile();
  const parse = useParseProfile();
  const update = useUpdateProfile();

  if (profile.isLoading || !profile.data) return <Spinner />;
  const p = profile.data;

  const text = (
    label: string,
    key: keyof typeof p,
    type: "text" | "number" = "text",
  ) => (
    <Field label={label} hint={p.locked_fields.includes(key as string) ? "edited — locked" : undefined}>
      <input
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        type={type}
        value={(p[key] as string | number | null) ?? ""}
        onChange={(e) =>
          update.mutate({
            [key]:
              type === "number"
                ? e.target.value === ""
                  ? null
                  : Number(e.target.value)
                : e.target.value,
          })
        }
      />
    </Field>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">
          {p.has_structured_parse
            ? "Parsed from your documents. Edit anything — your edits are kept on re-parse."
            : "Parse your uploaded documents to fill this in."}
        </p>
        <Button onClick={() => parse.mutate()} disabled={parse.isPending}>
          {parse.isPending ? "Parsing…" : p.has_structured_parse ? "Re-parse" : "Parse documents"}
        </Button>
      </div>
      {parse.error instanceof ApiError && <ErrorBox message={parse.error.message} />}

      <div className="grid gap-3 sm:grid-cols-2">
        {text("Full name", "full_name")}
        {text("Email", "email")}
        {text("University", "university")}
        {text("Programme", "program")}
        {text("Current semester", "current_semester", "number")}
        <Field label="Degree level">
          <Select
            value={p.degree_level ?? ""}
            onChange={(e) =>
              update.mutate({ degree_level: (e.target.value || null) as never })
            }
          >
            <option value="">—</option>
            <option value="bachelor">Bachelor</option>
            <option value="master">Master</option>
            <option value="phd">PhD</option>
          </Select>
        </Field>
        {text("Nationality", "nationality")}
      </div>

      <Field
        label="A cover letter you wrote yourself (optional)"
        hint="Used as a style sample so generated letters sound like you."
      >
        <textarea
          className="h-28 w-full rounded-md border border-slate-300 p-2 text-sm"
          defaultValue={p.voice_sample_text}
          onBlur={(e) => update.mutate({ voice_sample_text: e.target.value })}
        />
      </Field>

      <div>
        <div className="mb-1 text-sm font-medium text-slate-700">
          Skills ({p.skills.length})
        </div>
        <div className="flex flex-wrap gap-1">
          {p.skills.map((s) => (
            <span key={s.id} className="rounded bg-slate-100 px-2 py-0.5 text-xs">
              {s.name}
              {s.category === "language" && ` · ${s.evidence}`}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Search
export function SearchStep({ draft, set }: StepProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="City">
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.target_city ?? ""}
            onChange={(e) => set("target_city", e.target.value)}
          />
        </Field>
        <Field label="Radius (km)">
          <input
            type="number"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.radius_km ?? 30}
            onChange={(e) => set("radius_km", Number(e.target.value))}
          />
        </Field>
      </div>
      <Checkbox
        label="Include remote roles"
        checked={draft.allow_remote ?? true}
        onChange={(v) => set("allow_remote", v)}
      />
      <Field label="Target fields" hint="e.g. Data Science, Machine Learning">
        <TagInput
          values={draft.target_fields ?? []}
          onChange={(v) => set("target_fields", v)}
          placeholder="add a field…"
        />
      </Field>
      <Field label="Target job titles">
        <TagInput
          values={draft.target_titles ?? []}
          onChange={(v) => set("target_titles", v)}
          placeholder="Werkstudent Data Science…"
        />
      </Field>
      <Field label="Job types">
        <ChipToggle
          options={JOB_TYPES}
          values={draft.job_types ?? []}
          onChange={(v) => set("job_types", v)}
        />
      </Field>
    </div>
  );
}

// ----------------------------------------------------------------- Keywords
export function KeywordsStep({ draft, set }: StepProps) {
  const suggest = useSuggestKeywords();
  const suggestions = suggest.data;

  const move = (kw: string, to: "allow" | "block") => {
    const allow = new Set(draft.keywords_allow ?? []);
    const block = new Set(draft.keywords_block ?? []);
    allow.delete(kw);
    block.delete(kw);
    (to === "allow" ? allow : block).add(kw);
    set("keywords_allow", [...allow]);
    set("keywords_block", [...block]);
  };

  return (
    <div className="space-y-4">
      <Button
        onClick={() =>
          suggest.mutate({
            target_fields: draft.target_fields ?? [],
            target_titles: draft.target_titles ?? [],
          })
        }
        disabled={suggest.isPending}
      >
        {suggest.isPending ? "Thinking…" : "Suggest keywords"}
      </Button>
      {suggest.error instanceof ApiError && <ErrorBox message={suggest.error.message} />}

      {suggestions && (
        <div className="space-y-2 text-sm">
          {(["core", "adjacent", "tools", "likely_noise"] as const).map((group) => (
            <div key={group}>
              <div className="text-xs font-semibold text-slate-400 uppercase">{group}</div>
              <div className="flex flex-wrap gap-1">
                {suggestions[group].map((kw) => (
                  <span key={kw} className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs">
                    {kw}
                    <button className="text-green-600" onClick={() => move(kw, "allow")}>
                      +
                    </button>
                    <button className="text-red-500" onClick={() => move(kw, "block")}>
                      −
                    </button>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Field label="Allow-list" hint="Search terms you want">
        <TagInput
          values={draft.keywords_allow ?? []}
          onChange={(v) => set("keywords_allow", v)}
        />
      </Field>
      <Field label="Block-list" hint="Postings mentioning these are dropped">
        <TagInput
          values={draft.keywords_block ?? []}
          onChange={(v) => set("keywords_block", v)}
        />
      </Field>
    </div>
  );
}

// ------------------------------------------------------------------- Limits
export function LimitsStep({ draft, set }: StepProps) {
  const weights = draft.weights ?? {};
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Max weekly hours">
          <input
            type="number"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.hours_max ?? 20}
            onChange={(e) => set("hours_max", Number(e.target.value))}
          />
        </Field>
        <div className="flex items-end">
          <Checkbox
            label="Hard limit (drop jobs over it)"
            checked={draft.hours_hard ?? true}
            onChange={(v) => set("hours_hard", v)}
          />
        </div>
        <Field label="Max language level required">
          <Select
            value={draft.language_max_cefr ?? "B2"}
            onChange={(e) => set("language_max_cefr", e.target.value)}
          >
            {CEFR.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </Select>
        </Field>
        <div className="flex items-end">
          <Checkbox
            label="Hard limit"
            checked={draft.language_hard ?? false}
            onChange={(v) => set("language_hard", v)}
          />
        </div>
        <Field label="Only postings from the last N days">
          <input
            type="number"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.recency_days ?? 30}
            onChange={(e) => set("recency_days", Number(e.target.value))}
          />
        </Field>
      </div>

      <Field label="Acceptable contract types">
        <ChipToggle
          options={CONTRACT_TYPES}
          values={draft.contract_types ?? []}
          onChange={(v) => set("contract_types", v)}
        />
      </Field>
      <Checkbox
        label="Contract type is a hard limit"
        checked={draft.contract_type_hard ?? false}
        onChange={(v) => set("contract_type_hard", v)}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="“Recommended” threshold">
          <input
            type="number"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.score_threshold_recommend ?? 70}
            onChange={(e) => set("score_threshold_recommend", Number(e.target.value))}
          />
        </Field>
        <Field label="“Maybe” threshold">
          <input
            type="number"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.score_threshold_maybe ?? 55}
            onChange={(e) => set("score_threshold_maybe", Number(e.target.value))}
          />
        </Field>
      </div>

      <details className="rounded-md border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm font-medium">Score weights (advanced)</summary>
        <div className="mt-3 space-y-2">
          {WEIGHT_KEYS.map((k) => (
            <label key={k} className="flex items-center gap-3 text-sm">
              <span className="w-36 text-slate-600">{k}</span>
              <input
                type="range"
                min={0}
                max={40}
                value={weights[k] ?? 0}
                onChange={(e) =>
                  set("weights", { ...weights, [k]: Number(e.target.value) })
                }
                className="flex-1"
              />
              <span className="w-8 text-right">{weights[k] ?? 0}</span>
            </label>
          ))}
        </div>
      </details>
    </div>
  );
}

// ----------------------------------------------------------------- Schedule
export function ScheduleStep({ draft, set }: StepProps) {
  const channels = draft.notify_channels ?? [];
  const sources = draft.sources_enabled ?? {};
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Daily run time (HH:MM)">
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.run_time ?? "10:00"}
            onChange={(e) => set("run_time", e.target.value)}
          />
        </Field>
        <Field label="Timezone">
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.run_timezone ?? "Europe/Berlin"}
            onChange={(e) => set("run_timezone", e.target.value)}
          />
        </Field>
      </div>

      <Field label="Notifications">
        <ChipToggle
          options={[
            { value: "email", label: "Email" },
            { value: "telegram", label: "Telegram" },
          ]}
          values={channels}
          onChange={(v) => set("notify_channels", v)}
        />
      </Field>
      {channels.includes("email") && (
        <Field label="Notification email">
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.notify_email ?? ""}
            onChange={(e) => set("notify_email", e.target.value)}
          />
        </Field>
      )}
      {channels.includes("telegram") && (
        <Field label="Telegram chat id">
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={draft.notify_telegram_chat_id ?? ""}
            onChange={(e) => set("notify_telegram_chat_id", e.target.value)}
          />
        </Field>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Cover letter language">
          <Select
            value={draft.cover_letter_language_mode ?? "match_posting"}
            onChange={(e) =>
              set("cover_letter_language_mode", e.target.value as never)
            }
          >
            <option value="match_posting">Match the posting</option>
            <option value="always_de">Always German</option>
            <option value="always_en">Always English</option>
          </Select>
        </Field>
        <Field label="Cover letter tone">
          <Select
            value={draft.cover_letter_tone ?? "formal"}
            onChange={(e) => set("cover_letter_tone", e.target.value)}
          >
            <option value="formal">Formal</option>
            <option value="semi_formal">Semi-formal</option>
          </Select>
        </Field>
      </div>

      <details className="rounded-md border border-slate-200 p-3">
        <summary className="cursor-pointer text-sm font-medium">Job sources</summary>
        <div className="mt-3 grid gap-1 sm:grid-cols-2">
          {Object.keys(sources).map((key) => (
            <Checkbox
              key={key}
              label={key}
              checked={sources[key]}
              onChange={(v) => set("sources_enabled", { ...sources, [key]: v })}
            />
          ))}
        </div>
      </details>
    </div>
  );
}

// -------------------------------------------------------------- Eligibility
export function EligibilityStep({ draft, set }: StepProps) {
  const profile = useProfile();
  const update = useUpdateProfile();
  const terms = useSemesterTerms();
  const addTerm = useAddTerm();
  const delTerm = useDeleteTerm();
  const [label, setLabel] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  return (
    <div className="space-y-4">
      <Checkbox
        label="I'm a non-EU/EEA student — track my 140/280 working-day limit"
        checked={draft.eligibility_module_enabled ?? false}
        onChange={(v) => set("eligibility_module_enabled", v)}
      />
      {profile.data && (
        <Checkbox
          label="I am an EU / EEA citizen"
          checked={profile.data.is_eu_eea}
          onChange={(v) => update.mutate({ is_eu_eea: v })}
        />
      )}

      <div>
        <div className="mb-2 text-sm font-medium text-slate-700">
          Lecture periods (for the 20h/week rule)
        </div>
        <ul className="mb-2 space-y-1 text-sm">
          {(terms.data ?? []).map((t) => (
            <li key={t.id} className="flex items-center justify-between">
              <span>
                {t.label}: {t.lecture_start} → {t.lecture_end}
              </span>
              <Button variant="ghost" onClick={() => delTerm.mutate(t.id)}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-end gap-2">
          <input
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            placeholder="WS 2026/27"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <input type="date" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={start} onChange={(e) => setStart(e.target.value)} />
          <input type="date" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={end} onChange={(e) => setEnd(e.target.value)} />
          <Button
            variant="ghost"
            onClick={() => {
              if (label && start && end) {
                addTerm.mutate({ label, lecture_start: start, lecture_end: end });
                setLabel("");
                setStart("");
                setEnd("");
              }
            }}
          >
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Review
export function ReviewStep({ draft }: StepProps) {
  const summary = useMemo(
    () => [
      ["City", `${draft.target_city} (${draft.radius_km} km${draft.allow_remote ? " + remote" : ""})`],
      ["Fields", (draft.target_fields ?? []).join(", ") || "—"],
      ["Job types", (draft.job_types ?? []).join(", ") || "—"],
      ["Hours", `≤ ${draft.hours_max}${draft.hours_hard ? " (hard)" : ""}`],
      ["Daily run", `${draft.run_time} ${draft.run_timezone}`],
      ["Threshold", `recommend ≥ ${draft.score_threshold_recommend}`],
    ],
    [draft],
  );
  return (
    <Card>
      <dl className="space-y-1 text-sm">
        {summary.map(([k, v]) => (
          <div key={k} className="flex justify-between">
            <dt className="text-slate-500">{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export const STEPS: {
  key: string;
  title: string;
  component: (props: StepProps) => ReactNode;
}[] = [
  { key: "documents", title: "Documents", component: () => <DocumentsStep /> },
  { key: "profile", title: "Profile", component: () => <ProfileStep /> },
  { key: "search", title: "Where & what", component: (p) => <SearchStep {...p} /> },
  { key: "keywords", title: "Keywords", component: (p) => <KeywordsStep {...p} /> },
  { key: "limits", title: "Limits", component: (p) => <LimitsStep {...p} /> },
  { key: "schedule", title: "Schedule & alerts", component: (p) => <ScheduleStep {...p} /> },
  { key: "eligibility", title: "Eligibility", component: (p) => <EligibilityStep {...p} /> },
  { key: "review", title: "Review", component: (p) => <ReviewStep {...p} /> },
];

export function pickUpdatable(s: Settings): SettingsUpdate {
  const { target_lat: _lat, target_lon: _lon, ...rest } = s;
  void _lat;
  void _lon;
  return rest;
}
