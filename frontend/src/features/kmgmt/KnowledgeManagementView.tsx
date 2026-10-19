import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Database, Plus, Search, RefreshCw } from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";
import { KM_KPIS, SOURCES, SOURCE_IMPACT_WARNING, type Source, type SourceStatus } from "@/data/km";

const FILTERS: { value: SourceStatus | "all"; label: string }[] = [
  { value: "all", label: "All sources" },
  { value: "synced", label: "Synced" },
  { value: "partial", label: "Partial" },
];

function SourceDetails({ source }: { source: Source }) {
  const failed = source.failedPages ?? [];
  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <source.icon className="h-4 w-4 text-indigo-600" aria-hidden="true" />
          <h3 className="text-xs font-bold text-slate-800">{source.name}</h3>
        </div>
        <Tag variant={source.status === "synced" ? "emerald" : "amber"} shape="pill">
          {source.status === "synced" ? "Synced" : "Partial"}
        </Tag>
      </div>

      <div className="space-y-3 p-4 text-xs">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          {[
            ["Type", source.type],
            ["Indexed pages", source.indexed],
            ["Last successful sync", source.lastSync],
            ["Last attempt", source.lastAttempt ?? "—"],
            ["Owner", source.owner],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{k}</dt>
              <dd className="mt-0.5 font-semibold text-slate-700">{v}</dd>
            </div>
          ))}
        </dl>

        {failed.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-wide text-rose-500">
              Failed pages ({failed.length})
            </p>
            <div className="space-y-2">
              {failed.map((f) => (
                <div key={f.url} className="rounded-lg border border-rose-200 bg-rose-50 p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <code className="text-[11px] font-semibold text-rose-800">{f.url}</code>
                    <Tag variant="rose">{f.code}</Tag>
                  </div>
                  <p className="mt-1 text-[11px] font-bold text-rose-700">{f.reason}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-rose-600">{f.detail}</p>
                </div>
              ))}
            </div>
            <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-2.5">
              <div className="flex items-center gap-1.5 text-[11px] font-bold text-amber-800">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-600" aria-hidden="true" />
                Impact on answers
              </div>
              <p className="text-[11px] leading-relaxed text-amber-700">{SOURCE_IMPACT_WARNING}</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-auto flex items-center gap-2 border-t border-slate-100 px-4 py-3">
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Re-sync now
        </button>
        <button
          type="button"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
        >
          View indexed pages
        </button>
      </div>
    </div>
  );
}

export function KnowledgeManagementView() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<SourceStatus | "all">("all");
  const [selectedId, setSelectedId] = useState(SOURCES[0].id);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return SOURCES.filter(
      (s) =>
        (filter === "all" || s.status === filter) &&
        (q === "" || s.name.toLowerCase().includes(q) || s.type.toLowerCase().includes(q)),
    );
  }, [query, filter]);

  const selected = SOURCES.find((s) => s.id === selectedId) ?? SOURCES[0];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            Knowledge Management
          </h2>
          <p className="text-xs text-slate-500">
            Sources feeding the Knowledge Brain — what is indexed, what failed, and who owns it.
          </p>
        </div>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" aria-hidden="true" /> Add source
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {KM_KPIS.map((k) => (
          <div
            key={k.label}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div>
              <p className="text-2xl font-bold text-slate-900">{k.value}</p>
              <p className="mt-0.5 text-[11px] text-slate-500">{k.label}</p>
            </div>
            <div
              className={cn(
                "rounded-lg p-2.5",
                k.tone === "amber" ? "bg-amber-50 text-amber-600" : "bg-indigo-50 text-indigo-600",
              )}
            >
              <Database className="h-5 w-5" aria-hidden="true" />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Table */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5">
              <Search className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search sources"
                className="w-40 bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400"
                aria-label="Search sources"
              />
            </div>
            <div className="flex gap-1 rounded-md bg-slate-100 p-0.5">
              {FILTERS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => setFilter(f.value)}
                  className={cn(
                    "rounded px-2.5 py-1 text-[11px] font-bold transition",
                    filter === f.value
                      ? "bg-white text-slate-800 shadow-sm"
                      : "text-slate-500 hover:text-slate-700",
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="px-4 py-2.5 font-bold">Source</th>
                  <th className="px-3 py-2.5 font-bold">Type</th>
                  <th className="px-3 py-2.5 font-bold">Indexed</th>
                  <th className="px-3 py-2.5 font-bold">Status</th>
                  <th className="px-3 py-2.5 font-bold">Last sync</th>
                  <th className="px-4 py-2.5 font-bold">Owner</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => setSelectedId(s.id)}
                    className={cn(
                      "cursor-pointer transition hover:bg-slate-50",
                      s.id === selected.id && "bg-indigo-50/60",
                    )}
                  >
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-2">
                        <s.icon className="h-4 w-4 text-slate-400" aria-hidden="true" />
                        <span className="font-semibold text-slate-800">{s.name}</span>
                      </span>
                    </td>
                    <td className="px-3 py-3 text-slate-500">{s.type}</td>
                    <td className="px-3 py-3 font-medium text-slate-600">{s.indexed}</td>
                    <td className="px-3 py-3">
                      <Tag variant={s.status === "synced" ? "emerald" : "amber"}>
                        {s.status === "synced" ? "Synced" : "Partial"}
                      </Tag>
                    </td>
                    <td className="px-3 py-3 text-slate-500">{s.lastSync}</td>
                    <td className="px-4 py-3 text-slate-500">{s.owner}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                      No sources match your filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 text-[11px] text-slate-400">
            <span>
              {rows.length} of {SOURCES.length} sources
            </span>
            <span className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-emerald-500" aria-hidden="true" />
              Last full sync 17 Oct, 16:40
            </span>
          </div>
        </div>

        {/* Details */}
        <div className="lg:col-span-4">
          <SourceDetails source={selected} />
        </div>
      </div>
    </div>
  );
}
