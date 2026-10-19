import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Proposal } from "@/types/meeting";

function List({ title, items, tone }: { title: string; items: string[]; tone?: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className={`mb-1 text-xs font-semibold uppercase tracking-wide ${tone ?? "text-muted-foreground"}`}>{title}</p>
      <ul className="list-disc space-y-1 pl-5 text-sm">{items.map((i, idx) => <li key={idx}>{i}</li>)}</ul>
    </div>
  );
}

export function ProposalView({ proposal }: { proposal: Proposal }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={proposal.status === "approved" ? "success" : proposal.status === "draft" ? "secondary" : "info"}>
          {proposal.status}
        </Badge>
        <span className="text-xs text-muted-foreground">
          v{proposal.version} · {proposal.proposal_id}
        </span>
        {proposal.approved_by && (
          <span className="text-xs text-muted-foreground">approved by {proposal.approved_by}</span>
        )}
      </div>

      {proposal.approved_by === null && (
        <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning-foreground">
          Draft — not approved. A human must review before this proposal is final.
        </p>
      )}

      {proposal.overview && <p className="text-sm leading-relaxed">{proposal.overview}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs">In scope</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            {proposal.in_scope.length === 0 ? <p className="text-muted-foreground">—</p> :
              proposal.in_scope.map((s, i) => <p key={i}>• {s.description}</p>)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs">Out of scope</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            {proposal.out_of_scope.length === 0 ? <p className="text-muted-foreground">—</p> :
              proposal.out_of_scope.map((s, i) => <p key={i}>• {s.description}</p>)}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <List title="Business objectives" items={proposal.business_objectives} />
        <List title="Deliverables" items={proposal.deliverables.map((d) => d.name)} />
        <List title="Assumptions" items={proposal.assumptions} tone="text-warning-foreground" />
        <List title="Dependencies" items={proposal.dependencies} />
        <List title="Exclusions" items={proposal.exclusions} />
        <List title="Acceptance criteria" items={proposal.acceptance_criteria} />
        {proposal.open_questions.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Open questions</p>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {proposal.open_questions.map((q, i) => (
                <li key={i}>{q.blocking && <Badge variant="warning" className="mr-1">blocking</Badge>}{q.question}</li>
              ))}
            </ul>
          </div>
        )}
        {proposal.risks.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Risks</p>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {proposal.risks.map((r, i) => <li key={i}>{r.description} ({r.severity})</li>)}
            </ul>
          </div>
        )}
      </div>

      {proposal.estimates.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Estimates (provisional)</p>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                <tr><th className="px-3 py-2">Item</th><th className="px-3 py-2">Range</th><th className="px-3 py-2">Rationale</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {proposal.estimates.map((e, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2">{e.item}</td>
                    <td className="px-3 py-2 tabular-nums">{e.low}–{e.high} {e.unit}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{e.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {proposal.estimate_conditions.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">Conditions: {proposal.estimate_conditions.join("; ")}</p>
          )}
        </div>
      )}
    </div>
  );
}
