import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Rocket } from "lucide-react";
import { ApiError } from "@/api/client";
import { useSettings, useTriggerRun, useUpdateSettings } from "@/api/hooks";
import type { SettingsUpdate } from "@/api/types";
import { Button, Callout, Card, ErrorBox, Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";
import { STEPS, pickUpdatable } from "./steps";

const HINTS: Record<string, string> = {
  documents:
    "Your CV is what everything is matched against. It never leaves this machine except in the model calls you configure.",
  profile:
    "Parsed from your documents. Correct anything — edited fields are locked and a later re-parse won't overwrite them.",
  search: "Where to look and what kind of role you're after.",
  keywords:
    "Terms worth chasing, and words that should disqualify a posting outright.",
  limits:
    "Hard limits drop a posting entirely; everything else just moves the score.",
  schedule: "When the daily run fires and which sources it queries.",
  eligibility:
    "Optional. Only useful if you need to track the Werkstudent hours rule or the non-EU 140-day limit.",
  review: "One last look. Finishing kicks off your first search straight away.",
};

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

  const current = STEPS[step];
  const Step = current.component;
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
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-3xl space-y-6 p-6 py-10">
        <header>
          <h1 className="text-2xl font-bold tracking-tight">Set up FindMyJob</h1>
          <p className="mt-1 text-sm text-slate-500">
            A few minutes now, then it searches every morning and hands you a ranked
            shortlist. It never applies to anything for you.
          </p>
        </header>

        {/* step rail */}
        <ol className="flex flex-wrap gap-1">
          {STEPS.map((s, i) => {
            const done = i < step;
            const active = i === step;
            return (
              <li key={s.key} className="flex-1">
                <button
                  disabled={i > step}
                  onClick={() => setStep(i)}
                  className="w-full text-left disabled:cursor-default"
                >
                  <span
                    className={cn(
                      "block h-1 rounded-full transition-colors",
                      active ? "bg-slate-900" : done ? "bg-slate-400" : "bg-slate-200",
                    )}
                  />
                  <span
                    className={cn(
                      "mt-1.5 hidden text-[11px] font-medium sm:block",
                      active
                        ? "text-slate-900"
                        : done
                          ? "text-slate-500"
                          : "text-slate-300",
                    )}
                  >
                    {s.title}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>

        <Card
          title={`Step ${step + 1} of ${STEPS.length} · ${current.title}`}
          className="min-h-[22rem]"
        >
          {HINTS[current.key] && (
            <p className="-mt-2 mb-4 text-sm text-slate-500">{HINTS[current.key]}</p>
          )}
          <Step draft={draft} set={set} />
        </Card>

        {update.error instanceof ApiError && <ErrorBox message={update.error.message} />}

        {isLast && (
          <Callout tone="info" icon={Rocket}>
            Finishing saves everything and starts your first run. It takes a few
            minutes — you can watch it on the Today page.
          </Callout>
        )}

        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            icon={ArrowLeft}
            disabled={step === 0}
            onClick={() => setStep((s) => s - 1)}
          >
            Back
          </Button>
          <Button
            icon={isLast ? Check : ArrowRight}
            loading={update.isPending}
            onClick={next}
          >
            {isLast ? "Finish & run first search" : "Next"}
          </Button>
        </div>
      </div>
    </div>
  );
}
