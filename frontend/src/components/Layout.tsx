import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useLogout } from "@/api/hooks";
import { cn } from "@/lib/cn";
import { Button } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/tracker", label: "Tracker" },
  { to: "/runs", label: "Runs" },
  { to: "/settings", label: "Settings" },
];

export function Layout({ children }: { children: ReactNode }) {
  const logout = useLogout();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex max-w-6xl gap-6 p-6">
        <aside className="w-48 shrink-0">
          <div className="mb-6 text-lg font-bold">FindMyJob</div>
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-2 text-sm font-medium",
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-200",
                  )
                }
              >
                {item.label}
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
