// Каркас приложения: левый сайдбар с навигацией, контент справа.
// Острые углы, белый фон, тонкие линии 1px, акцент только для активного пункта.

import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import {
  Search,
  Building2,
  Upload,
  ListChecks,
  Unlink,
  LayoutDashboard,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/app", label: "Поиск", icon: Search, end: true },
  { to: "/app/partners", label: "Партнёры", icon: Building2 },
  { to: "/app/admin", label: "Загрузка", icon: Upload },
  { to: "/app/verification", label: "Очередь верификации", icon: ListChecks },
  { to: "/app/unmatched", label: "Несопоставленные", icon: Unlink },
  { to: "/app/dashboard", label: "Дашборд", icon: LayoutDashboard },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-white text-ink">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-line bg-white">
        <Link
          to="/"
          className="flex h-16 items-center border-b border-line px-5"
          aria-label="MedServicePrice, на главную"
        >
          <img
            src="/logo.png"
            alt="MedServicePrice"
            draggable={false}
            className="h-7 w-auto select-none"
          />
        </Link>

        <nav className="flex-1 overflow-y-auto p-3">
          <ul className="flex flex-col gap-1">
            {NAV.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      [
                        "flex items-center gap-3 rounded-sm border px-3 py-2 text-sm transition-colors",
                        isActive
                          ? "border-accent/30 bg-accent/5 font-medium text-accent"
                          : "border-transparent text-neutral-700 hover:bg-neutral-100",
                      ].join(" ")
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-line px-5 py-4 text-xs text-neutral-400">
          Архив прайс листов партнёров
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-6xl px-8 py-8">{children}</div>
      </main>
    </div>
  );
}

export default Layout;
