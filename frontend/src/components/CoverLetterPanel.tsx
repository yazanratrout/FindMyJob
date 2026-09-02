import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import {
  downloadCoverLetter,
  useCoverLetters,
  useGenerateCoverLetter,
  useRegenerateCoverLetter,
  useUpdateCoverLetter,
} from "@/api/hooks";
import type { CoverLetter, CoverLetterContent } from "@/api/types";
import { Button, ErrorBox, Spinner } from "./ui";

export function CoverLetterPanel({ jobId }: { jobId: number }) {
  const letters = useCoverLetters(jobId);
  const generate = useGenerateCoverLetter(jobId);
  const update = useUpdateCoverLetter(jobId);
  const regenerate = useRegenerateCoverLetter(jobId);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<CoverLetterContent | null>(null);
  const [instruction, setInstruction] = useState("");

  const list: CoverLetter[] = letters.data ?? [];
  const selected =
    list.find((l) => l.id === selectedId) ?? list[0] ?? null;

  useEffect(() => {
    if (selected) setDraft(structuredClone(selected.content));
  }, [selected?.id, selected?.version, selected]);

  if (letters.isLoading) return <Spinner />;

  const err = [generate.error, update.error, regenerate.error].find(
    (e) => e instanceof ApiError,
  ) as ApiError | undefined;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
          {generate.isPending
            ? "Drafting…"
            : list.length
              ? "New draft"
              : "Generate cover letter"}
        </Button>
        {list.length > 1 && (
          <select
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={selected?.id ?? ""}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {list.map((l) => (
              <option key={l.id} value={l.id}>
                v{l.version} {l.user_edited ? "(edited)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      {err && <ErrorBox message={err.message} />}

      {selected && draft && (
        <div className="space-y-3 rounded-md border border-slate-200 p-3">
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm font-semibold"
            value={draft.subject}
            onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
          />
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={draft.salutation}
            onChange={(e) => setDraft({ ...draft, salutation: e.target.value })}
          />
          {draft.paragraphs.map((p, i) => (
            <textarea
              key={i}
              className="h-24 w-full rounded border border-slate-300 p-2 text-sm"
              value={p}
              onChange={(e) => {
                const next = [...draft.paragraphs];
                next[i] = e.target.value;
                setDraft({ ...draft, paragraphs: next });
              }}
            />
          ))}
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={draft.closing}
            onChange={(e) => setDraft({ ...draft, closing: e.target.value })}
          />

          <details className="text-xs">
            <summary className="cursor-pointer font-medium text-slate-500">
              Claims used ({selected.claims_used.length}) — verify each
            </summary>
            <table className="mt-1 w-full">
              <tbody>
                {selected.claims_used.map((c, i) => (
                  <tr key={i} className="border-t border-slate-100 align-top">
                    <td className="w-1/2 py-1 pr-2">{c.claim}</td>
                    <td className="py-1 text-slate-500">{c.evidence_from_profile}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => update.mutate({ id: selected.id, content: draft })}
              disabled={update.isPending}
            >
              {update.isPending ? "Saving…" : "Save edits"}
            </Button>
            <Button variant="ghost" onClick={() => downloadCoverLetter(selected.id)}>
              Download .docx
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <input
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
              placeholder="Revision instruction (e.g. shorter, more about SQL)…"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
            />
            <Button
              variant="ghost"
              disabled={regenerate.isPending}
              onClick={() =>
                regenerate.mutate({
                  id: selected.id,
                  instruction: instruction.trim() || undefined,
                })
              }
            >
              {regenerate.isPending ? "…" : "Regenerate"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
