import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Bot,
  Building2,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  HelpCircle,
  Info,
  Menu,
  MoreVertical,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { NAV_SECTIONS, ROUTE_TITLES } from "@/lib/nav";
import { cn } from "@/lib/utils";

const PROJECTS = ["Northstar Logistics", "Acme Consulting", "Globex Manufacturing"];
const ACTIVE_PROJECT = "Northstar Logistics";

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-6 px-2" aria-label="Primary">
      {NAV_SECTIONS.map((section) => (
        <div key={section.title}>
          <div className="mb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {section.title}
          </div>
          <div className="space-y-1">
            {section.items.map(({ to, label, icon: Icon, count, countTone, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-slate-100 font-bold text-slate-900"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  )
                }
              >
                <span className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  <span>{label}</span>
                </span>
                {typeof count === "number" && (
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                      countTone === "amber" ? "bg-amber-100 text-amber-700" : "bg-indigo-100 text-indigo-700",
                    )}
                  >
                    {count}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      {/* Branding */}
      <div className="flex items-center gap-3 border-b border-slate-100 p-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-sm">
          <Bot className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-sm font-bold leading-tight text-slate-900">AI Tech Consultant</h1>
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Enterprise Workspace
          </p>
        </div>
      </div>

      {/* Org selector */}
      <div className="p-3">
        <button
          type="button"
          className="flex w-full cursor-pointer items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-2 transition hover:bg-slate-100"
        >
          <span className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-slate-200 text-xs font-bold text-slate-700">
              AC
            </span>
            <span className="text-xs font-semibold text-slate-700">Acme Consulting</span>
          </span>
          <ChevronsUpDown className="h-4 w-4 text-slate-400" aria-hidden="true" />
        </button>
      </div>

      <div className="mt-2 flex-1 overflow-y-auto scrollbar-thin">
        <SidebarNav onNavigate={onNavigate} />
      </div>

      {/* Bottom: shared brain + user */}
      <div className="space-y-3 border-t border-slate-200 p-3">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
          <div className="mb-1 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" aria-hidden="true" />
            <span className="text-xs font-bold text-slate-800">One shared Knowledge Brain</span>
          </div>
          <p className="text-[11px] leading-tight text-slate-500">
            Cited evidence for email drafts and meeting scopes.
          </p>
        </div>

        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
              AM
            </div>
            <div className="text-left">
              <div className="text-xs font-semibold leading-none text-slate-800">Alex Morgan</div>
              <div className="text-[10px] text-slate-400">Solution consultant</div>
            </div>
          </div>
          <MoreVertical className="h-4 w-4 cursor-pointer text-slate-400" aria-hidden="true" />
        </div>
      </div>
    </>
  );
}

function ProjectSelector() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 shadow-sm"
      >
        <Building2 className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
        <span className="font-medium">{ACTIVE_PROJECT}</span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-1 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {PROJECTS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setOpen(false)}
              className={cn(
                "flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors hover:bg-slate-50",
                p === ACTIVE_PROJECT ? "font-bold text-indigo-700" : "text-slate-700",
              )}
            >
              {p}
              {p === ACTIVE_PROJECT && <span className="text-[10px] text-slate-400">Active</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkspaceShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const title = ROUTE_TITLES[location.pathname] ?? "Dashboard";

  return (
    <div className="flex h-full flex-col overflow-hidden bg-slate-50 text-slate-800 antialiased">
      {/* Announcement banner */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-indigo-100 bg-indigo-50 px-4 py-1.5 text-xs text-indigo-700">
        <div className="flex items-center gap-2">
          <Info className="h-3.5 w-3.5 text-indigo-500" aria-hidden="true" />
          <span>
            <strong>SAMPLE WORKSPACE</strong> · Illustrative records, review states, and
            synchronization timestamps. Not connected to live systems.
          </span>
        </div>
        <div className="hidden items-center gap-4 text-indigo-600 md:flex">
          <span className="font-medium">{ACTIVE_PROJECT} context active</span>
          <button type="button" className="flex items-center gap-1 hover:underline">
            <RefreshCw className="h-3 w-3" aria-hidden="true" /> Sync status
          </button>
        </div>
      </div>

      <div className="flex h-full flex-1 overflow-hidden">
        {/* Desktop sidebar */}
        <aside className="z-20 hidden w-64 flex-shrink-0 flex-col justify-between border-r border-slate-200 bg-white lg:flex">
          <SidebarBody />
        </aside>

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
            <div
              className="absolute inset-0 bg-black/50"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <div className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white shadow-xl">
              <div className="flex justify-end p-2">
                <button
                  type="button"
                  onClick={() => setMobileOpen(false)}
                  aria-label="Close menu"
                  className="rounded-md p-1 text-slate-400 hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <SidebarBody onNavigate={() => setMobileOpen(false)} />
            </div>
          </div>
        )}

        {/* Main column */}
        <div className="flex h-full flex-1 flex-col overflow-hidden bg-slate-50">
          {/* Header */}
          <header className="z-10 flex h-12 flex-shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-6">
            <div className="flex items-center gap-2 text-xs">
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="rounded-md p-1 text-slate-400 hover:bg-slate-100 lg:hidden"
                aria-label="Open menu"
              >
                <Menu className="h-4 w-4" />
              </button>
              <span className="text-slate-400">Workspace</span>
              <ChevronRight className="h-3.5 w-3.5 text-slate-300" aria-hidden="true" />
              <span className="font-semibold text-slate-700">{title}</span>
            </div>

            <div className="flex items-center gap-4">
              <ProjectSelector />
              <span className="hidden text-xs font-medium text-slate-400 sm:inline">
                18 Oct 2026
              </span>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-600"
                aria-label="Help"
              >
                <HelpCircle className="h-4 w-4" />
              </button>
            </div>
          </header>

          {/* View content */}
          <main className="flex-1 overflow-y-auto p-4 scrollbar-thin sm:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
