import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  GitCompare,
  Inbox,
  Sparkles,
} from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";
import { QUEUE, type QueueItem } from "@/data/inbox";

type Decision = "approved" | "rejected";

const CITE_PATTERN = /\{\{(\d+)\}\}/g;

function renderDraft(text: string, citations: QueueItem["citations"]) {
  const parts = text.split(CITE_PATTERN);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      const marker = `[${part}]`;
      const label = citations.find((c) => c.marker === marker)?.label ?? `Source ${part}`;
      return (
        <sup
          key={i}
          title={label}
          className="mx-0.5 cursor-help rounded bg-indigo-100 px-1 py-px text-[10px] font-bold text-indigo-700"
        >
          {marker}
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function EvidenceDiagram() {
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wide text-slate-400">
        <span>Delivery attempt</span>
        <span>Backoff window</span>
      </div>
      {[
        { t: "Attempt 1", w: "Immediate", tone: "bg-emerald-100 text-emerald-700" },
        { t: "Attempt 2", w: "+2 min", tone: "bg-indigo-100 text-indigo-700" },
        { t: "Attempt 3", w: "+16 min", tone: "bg-indigo-100 text-indigo-700" },
        { t: "Final attempt", w: "≤ 24 hours", tone: "bg-amber-100 text-amber-700" },
      ].map((step) => (
        <div key={step.t} className="flex items-center gap-2 text-xs">
          <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold", step.tone)}>
            {step.t}
          </span>
          <span className="h-px flex-1 bg-slate-200" aria-hidden="true" />
          <span className="text-slate-500">{step.w}</span>
        </div>
      ))}
      <p className="pt-1 text-[11px] leading-tight text-slate-400">
        Exponential backoff · deliveries beyond 24 hours are dropped, not replayed.
      </p>
    </div>
  );
}

function EvidencePanel({ item }: { item: QueueItem }) {
  const [tab, setTab] = useState<"passage" | "diagram">("passage");
  const failed = item.evidence.section.includes("FAILED SYNC");

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-indigo-600" aria-hidden="true" />
          <h3 className="text-xs font-bold text-slate-800">Evidence</h3>
        </div>
        <Tag variant={failed ? "rose" : "emerald"} shape="pill">
          {failed ? "Failed sync" : "Matched"}
        </Tag>
      </div>

      <div className="flex gap-1 border-b border-slate-100 px-3 py-2">
        {(["passage", "diagram"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "rounded-md px-2.5 py-1 text-[11px] font-bold capitalize transition",
              tab === t
                ? "bg-slate-900 text-white"
                : "text-slate-500 hover:bg-slate-100",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin">
        <div>
          <div className="flex items-center gap-2">
            <Inbox className="h-4 w-4 text-slate-400" aria-hidden="true" />
            <span className="text-xs font-bold text-slate-800">{item.evidence.source}</span>
          </div>
          <p className="mt-0.5 text-[11px] text-slate-400">{item.evidence.section}</p>
        </div>

        {tab === "passage" ? (
          <div
            className={cn(
              "rounded-lg border p-3 text-xs leading-relaxed",
              failed
                ? "border-rose-200 bg-rose-50 text-rose-800"
                : "border-slate-200 bg-slate-50 text-slate-600",
            )}
          >
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">
              {failed ? "Retrieval result" : "Matched passage"}
            </p>
            <mark className="bg-transparent font-medium text-slate-900">
              {item.evidence.highlighted}
            </mark>
            <span>{item.evidence.rest}</span>
          </div>
        ) : (
          <EvidenceDiagram />
        )}

        {item.citations.length > 0 && (
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">
              Cited as
            </p>
            <div className="space-y-1.5">
              {item.citations.map((c) => (
                <div
                  key={c.marker}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                >
                  <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700">
                    {c.marker}
                  </span>
                  <span className="font-medium text-slate-700">{c.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function InboxAgentView() {
  const [selectedId, setSelectedId] = useState(QUEUE[0].id);
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [texts, setTexts] = useState<Record<string, string>>(() =>
    Object.fromEntries(QUEUE.map((q) => [q.id, q.draft.join("\n\n")])),
  );
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});

  const item = useMemo(() => QUEUE.find((q) => q.id === selectedId) ?? QUEUE[0], [selectedId]);
  const decision = decisions[item.id];

  const pendingCount = QUEUE.filter((q) => !decisions[q.id]).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Inbox Agent</h2>
          <p className="text-xs text-slate-500">
            AI drafts grounded in the Knowledge Brain. Every claim is cited before you send.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tag variant="indigo" shape="pill">
            {pendingCount} awaiting review
          </Tag>
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            Queue settings
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Queue */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-3">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <h3 className="text-xs font-bold text-slate-800">Review queue</h3>
            <span className="text-[10px] font-semibold text-slate-400">
              {QUEUE.length} threads
            </span>
          </div>
          <div className="divide-y divide-slate-100">
            {QUEUE.map((q) => {
              const decided = decisions[q.id];
              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setSelectedId(q.id)}
                  className={cn(
                    "w-full p-3 text-left transition",
                    q.id === item.id ? "bg-indigo-50/70" : "hover:bg-slate-50",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{q.sender}</span>
                    <span className="text-[10px] text-slate-400">{q.time}</span>
                  </div>
                  <p className="mt-0.5 truncate text-xs font-medium text-slate-600">
                    {q.subject}
                  </p>
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <Tag variant={q.badge === "escalated" ? "amber" : "indigo-soft"}>
                      {q.badge === "escalated" ? "Escalated" : "Needs review"}
                    </Tag>
                    {decided && (
                      <Tag variant={decided === "approved" ? "emerald" : "rose"}>
                        {decided === "approved" ? "Approved" : "Rejected"}
                      </Tag>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Center: original + draft */}
        <div className="space-y-4 lg:col-span-6">
          {/* Original email */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h3 className="text-xs font-bold text-slate-800">Original email</h3>
              <span className="text-[10px] text-slate-400">{item.projectRef}</span>
            </div>
            <pre className="whitespace-pre-wrap p-4 font-sans text-xs leading-relaxed text-slate-600">
              {item.original}
            </pre>
          </div>

          {/* AI draft */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-600" aria-hidden="true" />
                <h3 className="text-xs font-bold text-slate-800">AI draft</h3>
                <Tag variant="indigo-soft">{item.draftVersion}</Tag>
              </div>
              <div className="flex gap-1 rounded-md bg-slate-100 p-0.5">
                {(["preview", "edit"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMode(m)}
                    className={cn(
                      "rounded px-2 py-1 text-[11px] font-bold capitalize transition",
                      mode === m
                        ? "bg-white text-slate-800 shadow-sm"
                        : "text-slate-500 hover:text-slate-700",
                    )}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-4">
              {mode === "edit" ? (
                <textarea
                  value={texts[item.id]}
                  onChange={(e) =>
                    setTexts((prev) => ({ ...prev, [item.id]: e.target.value }))
                  }
                  rows={10}
                  className="w-full resize-y rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-700 outline-none focus:border-indigo-300 focus:bg-white"
                  aria-label="Edit AI draft"
                />
              ) : (
                <div className="space-y-3 text-xs leading-relaxed text-slate-700">
                  {texts[item.id]
                    .split("\n\n")
                    .map((para, i) => (
                      <p key={i}>{renderDraft(para, item.citations)}</p>
                    ))}
                </div>
              )}

              {item.removedClaim && (
                <div className="mt-4 space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800">
                    <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                    {item.removedClaim.title}
                  </div>
                  <p className="text-[11px] leading-relaxed text-amber-700">
                    {item.removedClaim.body}
                  </p>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
              <span className="text-[11px] text-slate-400">
                {decision === "approved"
                  ? "Approved — ready to send."
                  : decision === "rejected"
                    ? "Rejected — draft returned to the queue."
                    : "Review the evidence before approving."}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setDecisions((p) => ({ ...p, [item.id]: "rejected" }))}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
                >
                  <Ban className="h-3.5 w-3.5" aria-hidden="true" /> Reject
                </button>
                <button
                  type="button"
                  onClick={() => setDecisions((p) => ({ ...p, [item.id]: "approved" }))}
                  className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Approve & send
                </button>
              </div>
            </div>
          </div>

          {/* Removed claims / guardrail strip */}
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-[11px] text-slate-500">
            <GitCompare className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
            Drafts are regenerated from indexed sources only — unsupported claims are removed
            before you review.
          </div>
        </div>

        {/* Evidence */}
        <div className="lg:col-span-3">
          <EvidencePanel item={item} />
        </div>
      </div>
    </div>
  );
}
