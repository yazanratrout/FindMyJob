import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useLogout, useSettings, useUnseenDigestCount } from "@/api/hooks";
import { cn } from "@/lib/cn";
import { Button } from "./ui";

const NAV: { to: string; label: string; end?: boolean; badgeKey?: string }[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/activity", label: "Activity", badgeKey: "digests" },
  { to: "/tracker", label: "Tracker" },
  { to: "/runs", label: "Runs" },
  { to: "/settings", label: "Settings" },
];

export function Layout({ children }: { children: ReactNode }) {
  const logout = useLogout();
  const unseen = useUnseenDigestCount();
  const settings = useSettings();
  const nav = settings.data?.eligibility_module_enabled
    ? [...NAV.slice(0, 3), { to: "/eligibility", label: "Eligibility" }, ...NAV.slice(3)]
    : NAV;
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex max-w-6xl gap-6 p-6">
        <aside className="w-48 shrink-0">
          <div className="mb-6 text-lg font-bold">FindMyJob</div>
          <nav className="flex flex-col gap-1">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium",
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-200",
                  )
                }
              >
                {item.label}
                {item.badgeKey === "digests" &&
                  (unseen.data?.count ?? 0) > 0 && (
                    <span className="rounded-full bg-blue-600 px-1.5 text-xs text-white">
                      {unseen.data!.count}
                    </span>
                  )}
              </NavLink>
            ))}
          </nav>
          <Button
            variant="ghost"
            className="mt-6 w-full justify-start"
            onClick={() => logout.mutate()}
          >
            Log out
          </Button>
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
