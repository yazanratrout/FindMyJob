import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  CalendarClock,
  IdCard,
  KanbanSquare,
  LayoutDashboard,
  Loader2,
  LogOut,
  Settings as SettingsIcon,
} from "lucide-react";
import {
  useLatestRun,
  useLogout,
  useSettings,
  useUnseenDigestCount,
} from "@/api/hooks";
import { cn } from "@/lib/cn";
import { Button } from "./ui";

type NavItem = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  end?: boolean;
  badge?: "digests";
};

const NAV: NavItem[] = [
  { to: "/", label: "Today", icon: LayoutDashboard, end: true },
  { to: "/activity", label: "Activity", icon: Activity, badge: "digests" },
  { to: "/tracker", label: "Tracker", icon: KanbanSquare },
  { to: "/runs", label: "Runs", icon: CalendarClock },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

/** Live pipeline state, so you always know whether a run is working right now. */
function RunIndicator() {
  const run = useLatestRun();
  const latest = run.data;
  if (!latest) return null;

  if (latest.status === "running") {
    return (
      <NavLink
        to="/runs"
        className="flex items-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-xs font-medium text-indigo-700 ring-1 ring-indigo-200 ring-inset"
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Run #{latest.id} in progress
      </NavLink>
    );
  }
  const when = new Date(latest.finished_at ?? latest.started_at);
  const failed = latest.status === "failed";
  return (
    <NavLink
      to="/runs"
      className={cn(
        "flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium",
        failed ? "text-red-600 hover:bg-red-50" : "text-slate-500 hover:bg-slate-100",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          failed ? "bg-red-500" : "bg-emerald-500",
        )}
      />
      Last run {when.toLocaleDateString(undefined, { month: "short", day: "numeric" })}{" "}
      {when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
    </NavLink>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const logout = useLogout();
  const unseen = useUnseenDigestCount();
  const settings = useSettings();

  const nav: NavItem[] = settings.data?.eligibility_module_enabled
    ? [
        ...NAV.slice(0, 3),
        { to: "/eligibility", label: "Eligibility", icon: IdCard },
        ...NAV.slice(3),
      ]
    : NAV;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex max-w-7xl gap-8 p-6">
        <aside className="sticky top-6 flex h-[calc(100vh-3rem)] w-52 shrink-0 flex-col">
          <div className="mb-1 px-3 text-lg font-bold tracking-tight">FindMyJob</div>
          <p className="mb-6 px-3 text-xs text-slate-400">
            {settings.data?.target_city ?? "—"} · working-student search
          </p>

          <nav className="flex flex-col gap-0.5">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-200/70",
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
                {item.badge === "digests" && (unseen.data?.count ?? 0) > 0 && (
                  <span className="rounded-full bg-indigo-600 px-1.5 py-0.5 text-[10px] leading-none font-semibold text-white">
                    {unseen.data!.count}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="mt-auto space-y-1">
            <RunIndicator />
            <Button
              variant="ghost"
              size="sm"
              icon={LogOut}
              className="w-full justify-start"
              onClick={() => logout.mutate()}
            >
              Log out
            </Button>
          </div>
        </aside>

        <main className="min-w-0 flex-1 pb-12">{children}</main>
      </div>
    </div>
  );
}
