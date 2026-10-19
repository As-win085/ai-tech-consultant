import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle,
  GitCompare,
  Sparkles,
  Video,
  XCircle,
} from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";
import {
  TRANSCRIPT,
  SCOPE_DELTA,
  REQUIREMENTS,
  EFFORT,
  DELIVERABLES,
  type Requirement,
  type RequirementStatus,
  type EvidenceState,
} from "@/data/meeting";

const STATUS_TAG: Record<RequirementStatus, { label: string; variant: "emerald" | "indigo" | "amber" }> = {
  reviewed: { label: "Reviewed", variant: "emerald" },
  "ai-suggestion": { label: "AI suggestion", variant: "indigo" },
  "needs-clarification": { label: "Needs clarification", variant: "amber" },
};

const EVIDENCE: Record<
  EvidenceState,
  { label: string; tone: "emerald" | "amber" | "rose"; Icon: typeof CheckCircle }
> = {
  supported: { label: "Supported", tone: "emerald", Icon: CheckCircle },
  conditional: { label: "Conditional", tone: "amber", Icon: AlertCircle },
  unverified: { label: "Unverified · No supporting source", tone: "rose", Icon: XCircle },
};

const EVIDENCE_TEXT = {
  emerald: "text-emerald-600",
  amber: "text-amber-600",
  rose: "text-rose-600",
} as const;

function RequirementCard({ req }: { req: Requirement }) {
  const status = STATUS_TAG[req.status];
  const evidence = EVIDENCE[req.evidence];

  return (
    <div
      className={cn(
        "space-y-2 rounded-lg border p-3",
        req.flagged ? "border-amber-200 bg-amber-50/30" : "border-slate-200 bg-white",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase text-slate-400">{req.id}</span>
          <h4
            className={cn(
              "text-xs font-bold",
              req.flagged ? "text-amber-900" : "text-slate-900",
            )}
          >
            {req.title}
          </h4>
        </div>
        <Tag variant={status.variant}>{status.label}</Tag>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className={cn("flex items-center gap-1 font-medium", EVIDENCE_TEXT[evidence.tone])}>
          <evidence.Icon className="h-3.5 w-3.5" aria-hidden="true" /> {evidence.label}
          {req.evidenceCitation && (
            <a href="#" className="font-normal text-indigo-600 hover:underline">
              {" "}
              {req.evidenceCitation}
            </a>
          )}
        </span>
        <span
          className={cn("font-bold", req.effortExcluded ? "text-rose-700" : "text-slate-800")}
        >
          {req.effort}
        </span>
      </div>

      <p className={cn("text-[11px]", req.flagged ? "text-amber-800" : "text-slate-500")}>
        {req.assumption}
      </p>
    </div>
  );
}

export function MeetingToScopeView() {
  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-indigo-100 bg-indigo-50 text-indigo-600">
            <Video className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-bold text-slate-900">
                Northstar Logistics · Customer portal discovery
              </h2>
              <Tag variant="indigo-soft" shape="pill" className="border border-indigo-100">
                Scope v2 · Draft
              </Tag>
              <Tag variant="slate" shape="pill">
                1 reviewed / 5 requirements
              </Tag>
            </div>
            <p className="mt-0.5 text-xs text-slate-400">
              16 Oct 2026 · 42 min · Maya Chen, Jon Bell, Alex Morgan · Project NS-104
            </p>
          </div>
        </div>
        <button
          type="button"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        >
          Review draft scope
        </button>
      </div>

      {/* 3-column layout */}
      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-12">
        {/* Left: transcript + delta */}
        <div className="space-y-4 xl:col-span-3">
          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Transcript excerpt
            </h3>
            <div className="space-y-3 text-xs">
              {TRANSCRIPT.map((t) => (
                <div key={t.time} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                  <div className="mb-1 flex items-center justify-between text-[11px] font-semibold text-slate-500">
                    <span>{t.speaker}</span>
                    <span>{t.time}</span>
                  </div>
                  <p className="italic text-slate-700">“{t.text}”</p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 text-xs">
            <div className="flex items-center gap-1.5 font-bold text-indigo-900">
              <GitCompare className="h-4 w-4 text-indigo-600" aria-hidden="true" /> Requirement
              changes · v1 → v2
            </div>
            <div className="space-y-1 font-mono text-[11px] text-slate-700">
              {SCOPE_DELTA.map((line) => (
                <p
                  key={line.text}
                  className={cn(
                    line.kind === "added" && "text-emerald-700",
                    line.kind === "modified" && "text-amber-700",
                    line.kind === "unchanged" && "text-slate-500",
                  )}
                >
                  {line.text}
                </p>
              ))}
            </div>
          </div>
        </div>

        {/* Center: requirements matrix */}
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900">Extracted requirements</h3>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-600">
                {REQUIREMENTS.length}
              </span>
            </div>
            <button type="button" className="text-xs font-medium text-indigo-600 hover:underline">
              Review individually
            </button>
          </div>

          <p className="text-[11px] text-slate-400">
            AI suggestions are not commitments. Verify feasibility, evidence, and assumptions.
          </p>

          <div className="space-y-3">
            {REQUIREMENTS.map((req) => (
              <RequirementCard key={req.id} req={req} />
            ))}
          </div>

          {/* Effort */}
          <div className="border-t border-slate-100 pt-4">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Illustrative development effort
              </span>
              <span className="text-xs text-slate-400">{EFFORT.breakdown}</span>
            </div>
            <div className="text-2xl font-bold text-slate-900">{EFFORT.total}</div>
            <p className="text-[11px] text-slate-400">{EFFORT.note}</p>
          </div>

          {/* Review warning */}
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            <AlertTriangle
              className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600"
              aria-hidden="true"
            />
            <div>
              <strong>Estimate requires human review</strong>
              <p className="mt-0.5 text-[11px] text-amber-700">
                Assumes one portal, an existing auth layer, and sample payloads. Event volume,
                recovery needs, and access are still missing.
              </p>
            </div>
          </div>
        </div>

        {/* Right: proposed scope */}
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900">Proposed scope</h3>
            <Tag variant="slate">Draft v2</Tag>
          </div>

          <div className="border-b border-slate-100 pb-3">
            <h4 className="text-sm font-bold text-slate-900">
              RelayOps → Northstar Customer portal integration
            </h4>
            <p className="mt-0.5 text-xs text-slate-400">
              Prepared from 16 Oct discovery · Not approved
            </p>
          </div>

          <div className="space-y-3 text-xs">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Proposed deliverables
            </div>
            {DELIVERABLES.map((d) => (
              <div key={d.title} className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-indigo-600" aria-hidden="true" />
                <div>
                  <strong className="text-slate-800">{d.title}</strong>
                  <p className="text-[11px] text-slate-500">{d.detail}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Excluded */}
          <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs">
            <div className="flex items-center gap-1.5 font-bold text-amber-900">
              <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" /> Not included ·
              unresolved
            </div>
            <p className="text-[11px] leading-relaxed text-amber-800">
              EU-only hosting, historical migration, and guaranteed delivery beyond 24 hours. Do not
              approve these as committed scope.
            </p>
          </div>

          {/* Evidence callout */}
          <div className="space-y-1 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-1 text-[11px] font-bold uppercase text-indigo-600">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Knowledge Brain Evidence
            </div>
            <p className="text-xs italic text-slate-700">
              “Failed deliveries are retried... for <strong>up to 24 hours</strong>.”
            </p>
            <a href="#" className="inline-block text-[11px] font-medium text-indigo-600 hover:underline">
              [1] API guide · §4.2 · Inspect source →
            </a>
          </div>

          <p className="text-[11px] text-slate-400">
            Next: review the remaining suggestions and resolve hosting with Priya before scope
            sign-off.
          </p>
        </div>
      </div>
    </div>
  );
}
