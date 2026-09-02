import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { useSettings, useUpdateSettings } from "@/api/hooks";
import type { SettingsUpdate } from "@/api/types";
import { CalibrationPanel } from "@/components/CalibrationPanel";
import { Button, Card, ErrorBox, Spinner } from "@/components/ui";
import { STEPS, pickUpdatable } from "@/onboarding/steps";

export function SettingsPage() {
  const settings = useSettings();
  const update = useUpdateSettings();
  const [draft, setDraft] = useState<SettingsUpdate | null>(null);

  useEffect(() => {
    if (settings.data && !draft) setDraft(pickUpdatable(settings.data));
  }, [settings.data, draft]);

  if (!draft) return <Spinner />;

  const set = <K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <Button onClick={() => update.mutate(draft)} disabled={update.isPending}>
          {update.isPending ? "Saving…" : update.isSuccess ? "Saved" : "Save changes"}
        </Button>
      </div>
      {update.error instanceof ApiError && <ErrorBox message={update.error.message} />}

      {STEPS.filter((s) => s.key !== "review").map((s) => {
        const StepBody = s.component;
        return (
          <Card key={s.key} title={s.title}>
            <StepBody draft={draft} set={set} />
          </Card>
        );
      })}

      <CalibrationPanel />
    </div>
  );
}
