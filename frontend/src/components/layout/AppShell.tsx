import { BookOpen, Home, Settings, Sparkles } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { Logo } from "@/components/brand/Logo";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/context", label: "Context", icon: BookOpen },
  { to: "/studio", label: "Studio", icon: Sparkles },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  compact,
}: {
  to: string;
  label: string;
  icon: typeof Home;
  end?: boolean;
  compact?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
          compact && "flex-col gap-1 px-2 py-1.5 text-[11px]",
          isActive
            ? "bg-secondary text-foreground font-medium"
            : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
        )
      }
    >
      <Icon className={cn("size-4 shrink-0", compact && "size-5")} strokeWidth={1.75} />
      <span>{label}</span>
    </NavLink>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="hidden w-56 shrink-0 border-r border-border md:flex md:flex-col">
        <div className="flex items-center gap-2 border-b border-border px-4 py-4">
          <Logo variant="accent" className="size-7" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">ArtistAssist</p>
            <p className="truncate text-xs text-muted-foreground">Your social media assistant</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Main">
          {NAV.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3 md:hidden">
          <Logo variant="accent" className="size-6" />
          <span className="text-sm font-semibold">ArtistAssist</span>
        </header>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>

      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-background/95 backdrop-blur md:hidden"
        aria-label="Mobile"
      >
        {NAV.map((item) => (
          <div key={item.to} className="flex-1">
            <NavItem {...item} compact />
          </div>
        ))}
      </nav>
    </div>
  );
}
