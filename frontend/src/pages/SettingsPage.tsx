import { useEffect, useState } from "react";
import { Check, Save, SlidersHorizontal } from "lucide-react";
import { ApiError } from "@/api/client";
import { useSettings, useUpdateSettings } from "@/api/hooks";
import type { SettingsUpdate } from "@/api/types";
import { CalibrationPanel } from "@/components/CalibrationPanel";
import { Button, Callout, Card, ErrorBox, Spinner } from "@/components/ui";
import { STEPS, pickUpdatable } from "@/onboarding/steps";
import { cn } from "@/lib/cn";

const SECTION_HINTS: Record<string, string> = {
  documents: "Your CV and supporting files. Everything stays on this machine.",
  profile: "What the analyser matches postings against. Your edits are never overwritten.",
  search: "Where to look and what kind of role you want.",
  keywords: "Search terms to chase, and words that disqualify a posting outright.",
  limits: "Hard limits, score thresholds and how each component is weighted.",
  schedule: "When the daily run fires, and which sources it queries.",
  eligibility: "Optional Werkstudent / non-EU working-day tracking.",
};

export function SettingsPage() {
  const settings = useSettings();
  const update = useUpdateSettings();
  const [draft, setDraft] = useState<SettingsUpdate | null>(null);
  const [dirty, setDirty] = useState(false);
  const sections = STEPS.filter((s) => s.key !== "review");
  const [active, setActive] = useState(sections[0].key);

  useEffect(() => {
    if (settings.data && !draft) setDraft(pickUpdatable(settings.data));
  }, [settings.data, draft]);

  if (!draft) return <Spinner />;

  const set = <K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) => {
    setDirty(true);
    setDraft((d) => ({ ...d, [key]: value }));
  };

  const current = sections.find((s) => s.key === active) ?? sections[0];
  const StepBody = current.component;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="text-sm text-slate-500">
            Everything here is saved in your local database and used by the next run.
          </p>
        </div>
        <Button
          icon={update.isSuccess && !dirty ? Check : Save}
          loading={update.isPending}
          disabled={!dirty && !update.isPending}
          onClick={() => {
            update.mutate(draft, { onSuccess: () => setDirty(false) });
          }}
        >
          {update.isPending
            ? "Saving…"
            : dirty
              ? "Save changes"
              : update.isSuccess
                ? "Saved"
                : "No changes"}
        </Button>
      </header>

      {update.error instanceof ApiError && <ErrorBox message={update.error.message} />}
      {dirty && (
        <Callout tone="warn">You have unsaved changes on this page.</Callout>
      )}

      <div className="flex gap-6">
        <nav className="w-44 shrink-0 space-y-0.5">
          {sections.map((s) => (
            <button
              key={s.key}
              onClick={() => setActive(s.key)}
              className={cn(
                "block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors",
                active === s.key
                  ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
                  : "text-slate-600 hover:bg-slate-200/60",
              )}
            >
              {s.title}
            </button>
          ))}
          <button
            onClick={() => setActive("__calibration")}
            className={cn(
              "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors",
              active === "__calibration"
                ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
                : "text-slate-600 hover:bg-slate-200/60",
            )}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Calibration
          </button>
        </nav>

        <div className="min-w-0 flex-1">
          {active === "__calibration" ? (
            <CalibrationPanel />
          ) : (
            <Card title={current.title}>
              {SECTION_HINTS[current.key] && (
                <p className="-mt-2 mb-4 text-sm text-slate-500">
                  {SECTION_HINTS[current.key]}
                </p>
              )}
              <StepBody draft={draft} set={set} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
