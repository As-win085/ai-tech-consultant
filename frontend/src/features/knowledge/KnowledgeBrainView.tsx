import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Brain,
  CornerDownLeft,
  Flag,
  Plus,
  Search,
  Send,
  Sparkles,
} from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";
import { CONVERSATIONS, QUESTION, ANSWER, MISSING_EVIDENCE, EVIDENCE_PANEL } from "@/data/knowledge";

interface ExtraMessage {
  role: "user" | "assistant";
  text: string;
}

const EVIDENCE: Record<string, typeof EVIDENCE_PANEL> = {
  "[1]": EVIDENCE_PANEL,
  "[2]": {
    source: "Security overview",
    section: "Tenant isolation & audit retention · Last synced 17 Oct",
    passageLabel: "MATCHED PASSAGE · §3.1",
    passage:
      "Audit records are retained for 90 days and are tenant-isolated. No dedicated EU hosting region is identified in this revision.",
    related: { marker: "[1]", label: "API guide · §4.2 Delivery & retries" },
  },
};

const FOLLOW_UPS = [
  "What is required to validate signatures?",
  "Does the security overview mention EU regions?",
];

export function KnowledgeBrainView() {
  const [activeCitation, setActiveCitation] = useState<string>("[1]");
  const [tab, setTab] = useState<"passage" | "diagram">("passage");
  const [extras, setExtras] = useState<ExtraMessage[]>([]);
  const [input, setInput] = useState("");

  const evidence = EVIDENCE[activeCitation] ?? EVIDENCE_PANEL;

  const ask = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setExtras((prev) => [
      ...prev,
      { role: "user", text: trimmed },
      {
        role: "assistant",
        text: "This sample workspace ships one stored answer. In a live session this question would be answered from indexed sources with inline citations and an evidence panel.",
      },
    ]);
    setInput("");
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Knowledge Brain</h2>
          <p className="text-xs text-slate-500">
            Ask across synced sources. Answers cite the exact passage they came from.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tag variant="indigo" shape="pill">
            {ANSWER.citedSources} cited sources
          </Tag>
          <Tag variant="amber" shape="pill">
            {ANSWER.evidenceGaps} evidence gap
          </Tag>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Conversations */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-3">
          <div className="space-y-2 border-b border-slate-100 p-3">
            <button
              type="button"
              className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> New question
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5">
              <Search className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <input
                type="text"
                placeholder="Search conversations"
                className="w-full bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400"
                aria-label="Search conversations"
              />
            </div>
          </div>
          <div className="divide-y divide-slate-100">
            {CONVERSATIONS.map((c, i) => (
              <button
                key={c.id}
                type="button"
                className={cn(
                  "w-full px-4 py-3 text-left transition",
                  i === 0 ? "bg-indigo-50/70" : "hover:bg-slate-50",
                )}
              >
                <div className="flex items-center gap-2">
                  <Brain
                    className={cn(
                      "h-3.5 w-3.5",
                      i === 0 ? "text-indigo-600" : "text-slate-400",
                    )}
                    aria-hidden="true"
                  />
                  <span
                    className={cn(
                      "truncate text-xs",
                      i === 0 ? "font-bold text-slate-900" : "font-medium text-slate-700",
                    )}
                  >
                    {c.title}
                  </span>
                </div>
                <p className="mt-0.5 pl-[22px] text-[10px] text-slate-400">{c.meta}</p>
              </button>
            ))}
          </div>
          <div className="mt-auto border-t border-slate-100 p-3 text-[11px] leading-tight text-slate-400">
            Conversations stay scoped to the active project context.
          </div>
        </div>

        {/* Thread */}
        <div className="flex flex-col gap-4 lg:col-span-6">
          {/* Question */}
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-xl rounded-tr-sm border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-1 flex items-center justify-end gap-2 text-[11px]">
                <span className="text-slate-400">{QUESTION.time}</span>
                <span className="font-bold text-slate-700">{QUESTION.author}</span>
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-100 text-[9px] font-bold text-indigo-700">
                  AM
                </span>
              </div>
              <p className="text-xs leading-relaxed text-slate-700">{QUESTION.text}</p>
            </div>
          </div>

          {/* Answer */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-600" aria-hidden="true" />
                <h3 className="text-xs font-bold text-slate-800">Grounded answer</h3>
              </div>
              <span className="text-[10px] font-semibold text-slate-400">
                {ANSWER.citedSources} sources · {ANSWER.evidenceGaps} gap
              </span>
            </div>

            <div className="space-y-4 p-4">
              <p className="text-sm font-bold leading-relaxed text-slate-900">
                {ANSWER.headline}
              </p>

              <div className="space-y-3">
                {ANSWER.sections.map((s) => (
                  <p key={s.heading} className="text-xs leading-relaxed text-slate-600">
                    <span className="font-bold text-slate-800">{s.heading}</span> {s.body}{" "}
                    <button
                      type="button"
                      onClick={() => setActiveCitation(s.citation)}
                      className={cn(
                        "rounded px-1 py-0.5 align-baseline text-[10px] font-bold transition",
                        activeCitation === s.citation
                          ? "bg-indigo-600 text-white"
                          : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200",
                      )}
                      title="Show evidence for this citation"
                    >
                      {s.citation}
                    </button>
                  </p>
                ))}
              </div>

              {/* Missing evidence */}
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                  <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                  {MISSING_EVIDENCE.title}
                </div>
                <p className="text-[11px] leading-relaxed text-amber-800">
                  {MISSING_EVIDENCE.body}
                </p>
                <Link
                  to="/escalations"
                  className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-white px-2 py-1 text-[11px] font-bold text-amber-800 transition hover:bg-amber-100"
                >
                  <Flag className="h-3 w-3" aria-hidden="true" /> Review {MISSING_EVIDENCE.escalation}
                </Link>
              </div>
            </div>
          </div>

          {/* Extra messages */}
          {extras.map((m, i) => (
            <div
              key={i}
              className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-xl p-3 text-xs leading-relaxed",
                  m.role === "user"
                    ? "rounded-tr-sm border border-slate-200 bg-white text-slate-700 shadow-sm"
                    : "rounded-tl-sm border border-indigo-100 bg-indigo-50 text-slate-700",
                )}
              >
                {m.role === "assistant" && (
                  <span className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-indigo-500">
                    <Sparkles className="h-3 w-3" aria-hidden="true" /> Knowledge Brain
                  </span>
                )}
                {m.text}
              </div>
            </div>
          ))}

          {/* Follow-ups */}
          <div className="flex flex-wrap gap-2">
            {FOLLOW_UPS.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => ask(f)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-indigo-300 hover:text-indigo-700"
              >
                {f}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm focus-within:border-indigo-300">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask(input);
                  }
                }}
                rows={2}
                placeholder="Ask the Knowledge Brain… (Enter to send)"
                className="w-full resize-none bg-transparent px-1 text-xs leading-relaxed text-slate-700 outline-none placeholder:text-slate-400"
                aria-label="Ask the Knowledge Brain"
              />
              <button
                type="button"
                onClick={() => ask(input)}
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white transition hover:bg-indigo-700"
                aria-label="Send question"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <div className="mt-1 flex items-center gap-1.5 px-1 text-[10px] text-slate-400">
              <CornerDownLeft className="h-3 w-3" aria-hidden="true" />
              Answers are limited to indexed, evidence-backed sources.
            </div>
          </div>
        </div>

        {/* Evidence panel */}
        <div className="lg:col-span-3">
          <div className="flex h-full flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-600" aria-hidden="true" />
                <h3 className="text-xs font-bold text-slate-800">Evidence</h3>
              </div>
              <Tag variant="indigo-soft">{activeCitation}</Tag>
            </div>

            <div className="flex gap-1 border-b border-slate-100 px-3 py-2">
              {(["passage", "diagram"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-[11px] font-bold capitalize transition",
                    tab === t ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-100",
                  )}
                >
                  {t}
                </button>
              ))}
            </div>

            <div className="space-y-4 overflow-y-auto p-4">
              <div>
                <div className="flex items-center gap-2">
                  <Brain className="h-4 w-4 text-slate-400" aria-hidden="true" />
                  <span className="text-xs font-bold text-slate-800">{evidence.source}</span>
                </div>
                <p className="mt-0.5 text-[11px] text-slate-400">{evidence.section}</p>
              </div>

              {tab === "passage" ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">
                    {evidence.passageLabel}
                  </p>
                  <span className="font-medium text-slate-900">{evidence.passage}</span>
                </div>
              ) : (
                <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                  <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wide text-slate-400">
                    <span>Source</span>
                    <span>Claim</span>
                  </div>
                  {[evidence.source, "HMAC-SHA256 signing", "24-hour retry window", "90-day audit retention"].map(
                    (node) => (
                      <div
                        key={node}
                        className="rounded-md border border-slate-200 bg-white px-2 py-1.5 font-medium text-slate-700"
                      >
                        {node}
                      </div>
                    ),
                  )}
                  <p className="pt-1 text-[11px] leading-tight text-slate-400">
                    Citation graph: which sources support which claims.
                  </p>
                </div>
              )}

              <div>
                <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">
                  Related evidence
                </p>
                <button
                  type="button"
                  onClick={() => setActiveCitation(evidence.related.marker)}
                  className="flex w-full items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-2 text-left transition hover:border-indigo-200 hover:bg-indigo-50/50"
                >
                  <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700">
                    {evidence.related.marker}
                  </span>
                  <span className="text-[11px] font-medium leading-tight text-slate-600">
                    {evidence.related.label}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
