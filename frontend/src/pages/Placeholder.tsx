import { Card } from "@/components/ui";

export function PlaceholderPage({ title, note }: { title: string; note: string }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{title}</h1>
      <Card>
        <p className="text-sm text-slate-500">{note}</p>
      </Card>
    </div>
  );
}
