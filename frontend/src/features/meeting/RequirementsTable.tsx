import { useState } from "react";
import { ChevronDown, ChevronRight, Quote } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { FeasibilityBadge } from "@/components/shared/StatusPills";
import { cn } from "@/lib/utils";
import type { FeasibilityAssessment, Requirement } from "@/types/meeting";

const PRIORITY_VARIANT: Record<string, "destructive" | "warning" | "info" | "secondary"> = {
  high: "destructive",
  medium: "warning",
  low: "info",
  unspecified: "secondary",
};

function SourceRefs({ req }: { req: Requirement }) {
  if (req.source_refs.length === 0) {
    return <p className="text-xs text-muted-foreground">No source reference.</p>;
  }
  return (
    <ul className="space-y-2">
      {req.source_refs.map((ref) => (
        <li key={ref.segment_id} className="rounded border border-border bg-muted/40 p-2 text-xs">
          <p className="mb-1 flex items-center gap-1 font-medium text-muted-foreground">
            <Quote className="size-3" /> {ref.segment_id}
            {ref.speaker && <span className="font-normal">· {ref.speaker}</span>}
            {ref.timestamp && <span className="font-normal">· {ref.timestamp}</span>}
          </p>
          <p className="italic">“{ref.quote}”</p>
        </li>
      ))}
    </ul>
  );
}

export function RequirementsTable({
  requirements,
  feasibility,
}: {
  requirements: Requirement[];
  feasibility: Record<string, FeasibilityAssessment> | null | undefined;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (requirements.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border px-3 py-8 text-center text-sm text-muted-foreground">
        No requirements extracted yet. Ingest a transcript to populate this table.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-semibold">ID</th>
            <th className="px-3 py-2 font-semibold">Description</th>
            <th className="px-3 py-2 font-semibold">Type</th>
            <th className="px-3 py-2 font-semibold">Priority</th>
            <th className="px-3 py-2 font-semibold">Kind</th>
            <th className="px-3 py-2 font-semibold">Status</th>
            <th className="px-3 py-2 font-semibold">Feasibility</th>
            <th className="px-3 py-2 font-semibold">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {requirements.map((req) => {
            const feas = feasibility?.[req.requirement_id];
            const isOpen = expanded === req.requirement_id;
            return (
              <>
                <tr key={req.requirement_id} className="align-top hover:bg-accent/40">
                  <td className="px-3 py-2 font-mono text-xs">{req.requirement_id}</td>
                  <td className="max-w-xs px-3 py-2">{req.description}</td>
                  <td className="px-3 py-2">
                    <Badge variant="outline">{req.requirement_type.replace(/_/g, " ")}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={PRIORITY_VARIANT[req.priority] ?? "secondary"}>{req.priority}</Badge>
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{req.statement_kind}</td>
                  <td className="px-3 py-2">
                    <Badge variant="secondary">{req.status.replace(/_/g, " ")}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    {feas ? <FeasibilityBadge status={feas.status} /> : <span className="text-xs text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      onClick={() => setExpanded(isOpen ? null : req.requirement_id)}
                      aria-expanded={isOpen}
                    >
                      {isOpen ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                      {req.source_refs.length} ref{req.source_refs.length === 1 ? "" : "s"}
                    </button>
                  </td>
                </tr>
                {isOpen && (
                  <tr key={`${req.requirement_id}-detail`} className="bg-muted/20">
                    <td colSpan={8} className="px-3 py-3">
                      <div className="grid gap-4 lg:grid-cols-2">
                        <div>
                          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Transcript source references
                          </p>
                          <SourceRefs req={req} />
                        </div>
                        <div className="space-y-3 text-xs">
                          {req.acceptance_criteria.length > 0 && (
                            <div>
                              <p className="mb-1 font-semibold uppercase tracking-wide text-muted-foreground">Acceptance criteria</p>
                              <ul className="list-disc pl-5">{req.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
                            </div>
                          )}
                          {req.dependencies.length > 0 && (
                            <div>
                              <p className="mb-1 font-semibold uppercase tracking-wide text-muted-foreground">Dependencies</p>
                              <ul className="list-disc pl-5">{req.dependencies.map((c, i) => <li key={i}>{c}</li>)}</ul>
                            </div>
                          )}
                          {req.risks.length > 0 && (
                            <div>
                              <p className="mb-1 font-semibold uppercase tracking-wide text-muted-foreground">Risks</p>
                              <ul className="list-disc pl-5">{req.risks.map((c, i) => <li key={i}>{c}</li>)}</ul>
                            </div>
                          )}
                          <div>
                            <p className="mb-1 font-semibold uppercase tracking-wide text-muted-foreground">
                              Confidence: {req.confidence.level} ({req.confidence.score.toFixed(2)})
                            </p>
                            <p className="text-muted-foreground">{req.confidence.basis}</p>
                          </div>
                          {feas && (
                            <div>
                              <p className="mb-1 font-semibold uppercase tracking-wide text-muted-foreground">Feasibility detail</p>
                              {feas.answer && <p className="mb-1">{feas.answer}</p>}
                              {feas.citations.length > 0 && (
                                <ul className="space-y-0.5">
                                  {feas.citations.map((c, i) => (
                                    <li key={i} className="text-muted-foreground">
                                      • {c.title ?? c.chunk_id}
                                      {c.canonical_url && (
                                        <a href={c.canonical_url} target="_blank" rel="noreferrer" className="ml-1 text-primary hover:underline">
                                          source
                                        </a>
                                      )}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export { cn };
