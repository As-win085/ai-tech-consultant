import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ChangeTypeBadge } from "@/components/shared/StatusPills";
import { formatTimestamp } from "@/lib/utils";
import type { ChangeSummary } from "@/types/meeting";

export function ScopeChanges({ summaries }: { summaries: ChangeSummary[] }) {
  if (summaries.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border px-3 py-8 text-center text-sm text-muted-foreground">
        No scope changes recorded yet. Approve a baseline, ingest a follow-up transcript, then re-ingest to generate a comparison.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {summaries.map((summary, i) => (
        <div key={i} className="rounded-lg border border-border">
          <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-4 py-2.5 text-sm">
            <span className="font-medium">
              Baseline v{summary.from_baseline_version} → transcript {summary.to_transcript_id}
            </span>
            <span className="text-xs text-muted-foreground">{formatTimestamp(summary.generated_at)}</span>
            {summary.scope_creep_count > 0 && (
              <Badge variant="destructive" className="gap-1">
                <AlertTriangle className="size-3" /> {summary.scope_creep_count} scope creep
              </Badge>
            )}
          </div>
          {summary.changes.length === 0 ? (
            <p className="px-4 py-4 text-sm text-muted-foreground">No differences detected.</p>
          ) : (
            <ul className="divide-y divide-border">
              {summary.changes.map((c) => (
                <li key={c.change_id} className="px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <ChangeTypeBadge type={c.change_type} />
                    <span className="font-mono text-xs">{c.requirement_id}</span>
                    {c.scope_creep && <Badge variant="destructive">scope creep</Badge>}
                    <Badge variant="outline">{c.status.replace(/_/g, " ")}</Badge>
                  </div>
                  {c.summary && <p className="mt-1">{c.summary}</p>}
                  {c.rationale && <p className="mt-1 text-xs text-muted-foreground">Rationale: {c.rationale}</p>}
                  {(c.old_value || c.new_value) && (
                    <div className="mt-1.5 grid gap-2 text-xs sm:grid-cols-2">
                      {c.old_value && (
                        <p className="rounded bg-muted px-2 py-1"><span className="text-muted-foreground">Before:</span> {c.old_value}</p>
                      )}
                      {c.new_value && (
                        <p className="rounded bg-primary/10 px-2 py-1"><span className="text-muted-foreground">After:</span> {c.new_value}</p>
                      )}
                    </div>
                  )}
                  {c.estimate_impact && (
                    <p className="mt-1 text-xs text-warning-foreground">Estimate impact: {c.estimate_impact}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
