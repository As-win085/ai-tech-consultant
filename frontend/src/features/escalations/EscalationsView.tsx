import { Link } from "react-router-dom";
import { AlertTriangle, Flag, Globe, MessageSquare, ShieldQuestion } from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";

interface Escalation {
  id: string;
  title: string;
  status: "open" | "waiting";
  assignee: string;
  raisedBy: string;
  raisedAt: string;
  body: string;
  action: { label: string; to: string };
  tone: "amber" | "indigo";
}

const ESCALATIONS: Escalation[] = [
  {
    id: "ESC-12",
    title: "EU-only hosting cannot be confirmed",
    status: "open",
    assignee: "Priya Shah",
    raisedBy: "Knowledge Brain",
    raisedAt: "17 Oct, 16:32",
    body: "No indexed source confirms EU-only storage or processing for Northstar. The /help/regional-hosting page failed to sync (HTTP 403), so it cannot be cited. Until a source confirms regions, answers must qualify — or omit — the EU hosting commitment.",
    action: { label: "Open Knowledge Management", to: "/knowledge-management" },
    tone: "amber",
  },
  {
    id: "ESC-13",
    title: "Export API feasibility unverified",
    status: "waiting",
    assignee: "Alex Morgan",
    raisedBy: "Inbox Agent",
    raisedAt: "18 Oct, 08:56",
    body: "The security overview documents tenant-isolated audit access with 90-day retention, but no export endpoint. A tenant-scoped CSV export is proposed in scope v2 — confirm feasibility before committing it to the client.",
    action: { label: "Open Inbox Agent", to: "/inbox-agent" },
    tone: "indigo",
  },
];

export function EscalationsView() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Escalations</h2>
          <p className="text-xs text-slate-500">
            Claims the AI refuses to make without evidence. Each one needs a human decision.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tag variant="amber" shape="pill">
            2 open
          </Tag>
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            Filter by assignee
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {ESCALATIONS.map((esc) => (
          <div
            key={esc.id}
            className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex h-6 w-6 items-center justify-center rounded-md",
                    esc.tone === "amber" ? "bg-amber-100 text-amber-700" : "bg-indigo-100 text-indigo-700",
                  )}
                >
                  <Flag className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
                <span className="text-xs font-bold text-slate-900">{esc.id}</span>
                <Tag variant={esc.status === "open" ? "amber" : "indigo-soft"}>
                  {esc.status === "open" ? "Open" : "Waiting on source"}
                </Tag>
              </div>
              <span className="text-[10px] text-slate-400">{esc.raisedAt}</span>
            </div>

            <div className="flex-1 space-y-3 p-4">
              <h3 className="text-sm font-bold text-slate-900">{esc.title}</h3>
              <p className="text-xs leading-relaxed text-slate-600">{esc.body}</p>

              <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3 text-[11px]">
                <div>
                  <p className="font-bold uppercase tracking-wide text-slate-400">Raised by</p>
                  <p className="mt-0.5 font-semibold text-slate-700">{esc.raisedBy}</p>
                </div>
                <div>
                  <p className="font-bold uppercase tracking-wide text-slate-400">Assignee</p>
                  <p className="mt-0.5 font-semibold text-slate-700">{esc.assignee}</p>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
              <Link
                to={esc.action.to}
                className="text-xs font-semibold text-indigo-600 hover:underline"
              >
                {esc.action.label} →
              </Link>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:bg-slate-50"
                >
                  Request source
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-slate-900 px-3 py-1.5 text-[11px] font-semibold text-white transition hover:bg-slate-700"
                >
                  Resolve
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* How escalations work */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          {
            icon: AlertTriangle,
            title: "Raised automatically",
            body: "When a claim has no evidence in any synced source, the AI blocks it and files an escalation.",
          },
          {
            icon: Globe,
            title: "Often a sync problem",
            body: "Failed pages are the usual cause — re-syncing the source can clear the escalation.",
          },
          {
            icon: ShieldQuestion,
            title: "Resolved by a human",
            body: "An owner confirms the fact or rejects it. Resolutions become citable context.",
          },
        ].map((c) => (
          <div key={c.title} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
              <c.icon className="h-4 w-4" aria-hidden="true" />
            </div>
            <h4 className="text-xs font-bold text-slate-800">{c.title}</h4>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{c.body}</p>
          </div>
        ))}
      </div>

      <p className="flex items-center gap-1.5 text-[11px] text-slate-400">
        <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
        Resolved escalations appear in Feedback History with the decision rationale.
      </p>
    </div>
  );
}
