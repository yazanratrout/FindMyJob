import { useEffect, useState } from "react";
import { useSettings, useTriggerRun, useUpdateSettings } from "@/api/hooks";
import type { SettingsUpdate } from "@/api/types";
import { Button, ErrorBox, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";
import { STEPS, pickUpdatable } from "./steps";
import { ApiError } from "@/api/client";

export function OnboardingWizard() {
  const settings = useSettings();
  const update = useUpdateSettings();
  const trigger = useTriggerRun();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<SettingsUpdate | null>(null);

  useEffect(() => {
    if (settings.data && !draft) setDraft(pickUpdatable(settings.data));
  }, [settings.data, draft]);

  if (!draft) return <Spinner />;

  const set = <K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const Step = STEPS[step].component;
  const isLast = step === STEPS.length - 1;

  const next = async () => {
    await update.mutateAsync(draft);
    if (isLast) {
      await update.mutateAsync({ onboarding_completed: true });
      trigger.mutate(undefined);
    } else {
      setStep((s) => s + 1);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="flex gap-1">
        {STEPS.map((s, i) => (
          <div
            key={s.key}
            className={cn(
              "h-1 flex-1 rounded",
              i <= step ? "bg-slate-900" : "bg-slate-200",
            )}
          />
        ))}
      </div>
      <div>
        <div className="text-xs font-semibold text-slate-400 uppercase">
          Step {step + 1} of {STEPS.length}
        </div>
        <h1 className="text-xl font-bold">{STEPS[step].title}</h1>
      </div>

      <Step draft={draft} set={set} />

      {update.error instanceof ApiError && <ErrorBox message={update.error.message} />}

      <div className="flex justify-between border-t border-slate-200 pt-4">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          Back
        </Button>
        <Button onClick={next} disabled={update.isPending}>
          {update.isPending
            ? "Saving…"
            : isLast
              ? "Finish & run first search"
              : "Next"}
        </Button>
      </div>
    </div>
  );
}
