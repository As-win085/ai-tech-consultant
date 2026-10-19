import { useNavigate, Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Inbox, Layers } from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";
import { METRICS, ATTENTION_ITEMS, SYNC_ROWS, CLIENT_CONTEXT } from "@/data/dashboard";

const ICON_TONES = {
  indigo: "bg-indigo-50 text-indigo-600",
  amber: "bg-amber-50 text-amber-600",
  rose: "bg-rose-50 text-rose-600",
} as const;

const BADGE_TONES = {
  indigo: "bg-indigo-50 text-indigo-700",
  amber: "bg-amber-50 text-amber-700",
} as const;

export function DashboardView() {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard</h2>
          <p className="text-xs text-slate-500">Your review desk for Northstar Logistics.</p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/inbox-agent")}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-indigo-700"
        >
          <Inbox className="h-4 w-4" aria-hidden="true" /> Open review queue
        </button>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {METRICS.map((m) => (
          <div
            key={m.label}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div>
              <p className="text-xs font-medium text-slate-500">{m.label}</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">{m.value}</p>
              <p
                className={cn(
                  "mt-0.5 text-[11px]",
                  m.subTone === "amber" ? "text-amber-600" : "text-slate-400",
                )}
              >
                {m.sub}
              </p>
            </div>
            <div className={cn("rounded-lg p-2.5", ICON_TONES[m.iconTone])}>
              <m.icon className="h-5 w-5" aria-hidden="true" />
            </div>
          </div>
        ))}
      </div>

      {/* Priority + sync layout */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Needs your attention */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm xl:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-800">Needs your attention</h3>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                7 items
              </span>
            </div>
            <Link
              to="/inbox-agent"
              className="text-xs font-medium text-indigo-600 hover:underline"
            >
              View all reviews →
            </Link>
          </div>

          <div className="divide-y divide-slate-100">
            {ATTENTION_ITEMS.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-4 transition hover:bg-slate-50/80"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      "mt-0.5 rounded-lg p-2",
                      item.iconTone === "amber" ? "bg-amber-50 text-amber-600" : "bg-indigo-50 text-indigo-600",
                    )}
                  >
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">{item.title}</h4>
                    <p className="text-xs text-slate-500">{item.meta}</p>
                    <p className="mt-1 text-[11px] text-slate-400">{item.time}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={cn(
                      "mb-1 inline-block rounded px-2 py-0.5 text-[10px] font-semibold",
                      BADGE_TONES[item.badge.tone],
                    )}
                  >
                    {item.badge.label}
                  </span>
                  <div>
                    <button
                      type="button"
                      onClick={() => navigate(item.actionTo)}
                      className="text-xs font-semibold text-indigo-600 hover:underline"
                    >
                      {item.actionLabel} →
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right column: sync + client context */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-800">Source synchronization</h3>
              <Link
                to="/knowledge-management"
                className="text-xs font-medium text-indigo-600 hover:underline"
              >
                Manage sources →
              </Link>
            </div>

            <div className="mb-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">7 of 8</span>
              <Tag variant="amber" shape="pill">
                1 partial sync
              </Tag>
            </div>
            <p className="mb-4 text-xs text-slate-500">sources fully synchronized</p>

            <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <div className="flex items-center gap-1.5 font-bold">
                <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                RelayOps help center
              </div>
              <p className="text-[11px] text-amber-700">
                2 pages could not be retrieved. Existing indexed pages remain available.
              </p>
            </div>

            <div className="mt-4 space-y-2">
              {SYNC_ROWS.map((row) => (
                <div
                  key={row.name}
                  className="flex items-center justify-between border-b border-slate-100 py-1 text-xs"
                >
                  <span className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />
                    <span className="font-medium text-slate-700">{row.name}</span>
                  </span>
                  <span className="text-[11px] text-slate-400">{row.at}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Client context */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
              Current client context
            </h3>
            <div className="mb-2 flex items-center gap-2">
              <Layers className="h-4 w-4 text-indigo-600" aria-hidden="true" />
              <span className="text-sm font-bold text-slate-900">{CLIENT_CONTEXT.name}</span>
            </div>
            <p className="mb-3 text-xs leading-relaxed text-slate-600">{CLIENT_CONTEXT.summary}</p>
            <div className="flex items-center justify-between border-t border-slate-100 pt-2 text-[11px] text-slate-400">
              <span>
                Owner: <strong className="text-slate-700">{CLIENT_CONTEXT.owner}</strong>
              </span>
              <span>{CLIENT_CONTEXT.project}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
