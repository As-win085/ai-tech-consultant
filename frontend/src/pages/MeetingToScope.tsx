import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, CheckCircle2, FileSignature, GitCompare, ScrollText } from "lucide-react";
import { meetingApi, type TranscriptCreatePayload } from "@/api/meeting";
import { ApiError } from "@/api/http";
import type { FeasibilityAssessment } from "@/types/meeting";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConnectivityBadge } from "@/components/shared/StatusPills";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/StateViews";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { TranscriptIngest } from "@/features/meeting/TranscriptIngest";
import { RequirementsTable } from "@/features/meeting/RequirementsTable";
import { ProposalView } from "@/features/meeting/ProposalView";
import { ScopeChanges } from "@/features/meeting/ScopeChanges";

type Tab = "requirements" | "proposal" | "scope" | "history";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "requirements", label: "Requirements", icon: <ScrollText className="size-4" /> },
  { id: "proposal", label: "Proposal / SOW", icon: <FileSignature className="size-4" /> },
  { id: "scope", label: "Baseline & scope", icon: <GitCompare className="size-4" /> },
  { id: "history", label: "History", icon: <CalendarRange className="size-4" /> },
];

export function MeetingPage() {
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [showIngest, setShowIngest] = useState(false);
  const [tab, setTab] = useState<Tab>("requirements");
  const [reviewer, setReviewer] = useState("reviewer-1");

  const ready = useQuery({
    queryKey: ["meeting", "ready"],
    queryFn: () => meetingApi.ready(),
    retry: 1,
  });

  const projects = useQuery({
    queryKey: ["meeting", "projects"],
    queryFn: () => meetingApi.listProjects(),
    retry: 1,
  });

  const requirements = useQuery({
    queryKey: ["meeting", "requirements", projectId],
    queryFn: ({ signal }) => meetingApi.listRequirements(projectId!, signal),
    enabled: Boolean(projectId),
    retry: 1,
  });

  const baselines = useQuery({
    queryKey: ["meeting", "baselines", projectId],
    queryFn: ({ signal }) => meetingApi.listBaselines(projectId!, signal),
    enabled: Boolean(projectId),
    retry: 1,
  });

  const changes = useQuery({
    queryKey: ["meeting", "changes", projectId],
    queryFn: ({ signal }) => meetingApi.listChangeSummaries(projectId!, signal),
    enabled: Boolean(projectId),
    retry: 1,
  });

  const events = useQuery({
    queryKey: ["meeting", "events", projectId],
    queryFn: ({ signal }) => meetingApi.listEvents(projectId!, signal),
    enabled: Boolean(projectId),
    retry: 1,
  });

  const ingest = useMutation({
    mutationFn: (payload: TranscriptCreatePayload) => meetingApi.ingestTranscript(payload),
    onSuccess: (result) => {
      setProjectId(result.transcript.project_id);
      setShowIngest(false);
      queryClient.invalidateQueries({ queryKey: ["meeting", "projects"] });
      queryClient.invalidateQueries({ queryKey: ["meeting", "requirements"] });
      queryClient.invalidateQueries({ queryKey: ["meeting", "changes"] });
    },
  });

  const [feasibilityResult, setFeasibilityResult] = useState<Record<string, FeasibilityAssessment> | null>(null);
  const feasibility = useMutation({
    mutationFn: (id: string) => meetingApi.assessFeasibility(id),
    onSuccess: (data) => {
      setFeasibilityResult(data);
      queryClient.invalidateQueries({ queryKey: ["meeting", "requirements"] });
    },
  });

  const [proposalId, setProposalId] = useState<string | null>(null);
  const generateProposal = useMutation({
    mutationFn: (id: string) => meetingApi.createProposal(id, {}),
    onSuccess: (p) => {
      setProposalId(p.proposal_id);
      setTab("proposal");
    },
  });

  const proposal = useQuery({
    queryKey: ["meeting", "proposal", proposalId],
    queryFn: ({ signal }) => meetingApi.getProposal(proposalId!, signal),
    enabled: Boolean(proposalId),
    retry: 1,
  });

  const createBaseline = useMutation({
    mutationFn: (id: string) => meetingApi.createBaseline(id, { approved_by: reviewer, note: "Baseline approved from console" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meeting", "baselines"] });
      setTab("scope");
    },
  });

  const approveUpdate = useMutation({
    mutationFn: ({ id, transcriptId }: { id: string; transcriptId: string }) =>
      meetingApi.approveBaselineUpdate(id, transcriptId, reviewer),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meeting", "baselines"] }),
  });

  const activeBaselines = baselines.data ?? [];

  const projectList = projects.data?.projects ?? [];
  const kbReachable = ready.data?.knowledge_brain_reachable;

  return (
    <div>
      <PageHeader
        title="Meeting-to-Scope"
        description="Turn meeting transcripts into traceable requirements, Knowledge Brain feasibility checks, a draft statement of work, and a versioned baseline that only changes through explicit human approval."
        actions={
          <div className="flex items-center gap-2">
            <ConnectivityBadge online={ready.data ? kbReachable !== false : null} label={ready.data ? (kbReachable ? "KB reachable" : "KB unreachable") : "Checking…"} />
            <Button size="sm" variant="outline" onClick={() => setShowIngest((s) => !s)}>
              {showIngest ? "Hide ingest" : "Ingest transcript"}
            </Button>
          </div>
        }
      />

      {showIngest && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Ingest a transcript</CardTitle>
          </CardHeader>
          <CardContent>
            <TranscriptIngest onIngest={(p) => ingest.mutate(p)} ingesting={ingest.isPending} />
            {ingest.isError && (
              <ErrorState
                className="mt-3"
                title="Ingestion failed"
                message={ingest.error instanceof ApiError ? ingest.error.message : "Unknown error."}
                requestId={ingest.error instanceof ApiError ? ingest.error.requestId : undefined}
              />
            )}
            {ingest.isSuccess && (
              <Alert variant={ingest.data.idempotent ? "info" : "success"} className="mt-3">
                <CheckCircle2 />
                <AlertTitle>{ingest.data.idempotent ? "Already ingested (idempotent)" : "Transcript ingested"}</AlertTitle>
                <AlertDescription>
                  Extracted {ingest.data.requirements.length} requirement
                  {ingest.data.requirements.length === 1 ? "" : "s"}.
                  {ingest.data.warnings.length > 0 && ` Warnings: ${ingest.data.warnings.join("; ")}`}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        {/* Project sidebar */}
        <Card className="h-max">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs">Projects</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {projects.isLoading ? (
              <LoadingState lines={3} />
            ) : projects.isError ? (
              <ErrorState
                title="Unreachable"
                message={projects.error instanceof ApiError ? projects.error.message : "Meeting service offline."}
                onRetry={() => projects.refetch()}
              />
            ) : projectList.length === 0 ? (
              <p className="text-xs text-muted-foreground">No projects yet. Ingest a transcript.</p>
            ) : (
              projectList.map((p, i) => {
                const id = String(p["project_id"] ?? i);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      setProjectId(id);
                      setProposalId(null);
                    }}
                    className={cn(
                      "w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent",
                      projectId === id && "bg-primary/10 font-medium text-primary",
                    )}
                  >
                    {id}
                  </button>
                );
              })
            )}
            <div className="mt-3 space-y-1.5 border-t border-border pt-3">
              <Label htmlFor="reviewer">Reviewer actor</Label>
              <Input id="reviewer" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
              <p className="text-[11px] text-muted-foreground">
                This value is caller-supplied and is not identity-verified by the backend.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Main workspace */}
        <div>
          {!projectId ? (
            <EmptyState
              title="Select a project"
              description="Choose a project from the left, or ingest a transcript to begin."
            />
          ) : (
            <>
              <div className="mb-4 flex flex-wrap gap-1 border-b border-border">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={cn(
                      "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                      tab === t.id
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.icon}
                    {t.label}
                  </button>
                ))}
              </div>

              {tab === "requirements" && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => feasibility.mutate(projectId)} loading={feasibility.isPending}>
                      Assess feasibility (via Knowledge Brain)
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => generateProposal.mutate(projectId)}
                      loading={generateProposal.isPending}
                    >
                      Generate proposal
                    </Button>
                  </div>
                  {feasibility.isError && (
                    <ErrorState
                      title="Feasibility assessment failed"
                      message={feasibility.error instanceof ApiError ? feasibility.error.message : "Unknown error."}
                      onRetry={() => feasibility.mutate(projectId)}
                    />
                  )}
                  {feasibility.isSuccess && (
                    <Alert variant="success">
                      <CheckCircle2 />
                      <AlertTitle>Feasibility assessed</AlertTitle>
                      <AlertDescription>
                        Knowledge Brain evidence applied to requirements. Expand a row to read citations.
                      </AlertDescription>
                    </Alert>
                  )}
                  {requirements.isLoading ? (
                    <LoadingState lines={6} />
                  ) : requirements.isError ? (
                    <ErrorState
                      message={requirements.error instanceof ApiError ? requirements.error.message : "Could not load requirements."}
                      onRetry={() => requirements.refetch()}
                    />
                  ) : (
                    <RequirementsTable requirements={requirements.data ?? []} feasibility={feasibilityResult} />
                  )}
                </div>
              )}

              {tab === "proposal" && (
                <div className="space-y-3">
                  {!proposalId ? (
                    <EmptyState
                      title="No proposal generated"
                      description="Generate a draft proposal from the Requirements tab."
                      action={
                        <Button size="sm" onClick={() => generateProposal.mutate(projectId)} loading={generateProposal.isPending}>
                          Generate proposal
                        </Button>
                      }
                    />
                  ) : proposal.isLoading ? (
                    <LoadingState lines={8} />
                  ) : proposal.isError ? (
                    <ErrorState message={proposal.error instanceof ApiError ? proposal.error.message : "Could not load proposal."} onRetry={() => proposal.refetch()} />
                  ) : proposal.data ? (
                    <ProposalView proposal={proposal.data} />
                  ) : null}
                </div>
              )}

              {tab === "scope" && (
                <div className="space-y-4">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm">Baseline</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {activeBaselines.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          No baseline frozen yet. Approving a baseline snapshots the current requirements so later changes can be diffed.
                        </p>
                      ) : (
                        <ul className="space-y-1.5 text-sm">
                          {activeBaselines.map((b) => (
                            <li key={b.baseline_id} className="flex items-center justify-between rounded border border-border px-3 py-2">
                              <span>v{b.version} · {b.status}</span>
                              <span className="text-xs text-muted-foreground">
                                {b.approved_by ? `by ${b.approved_by}` : "pending"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <Button size="sm" onClick={() => createBaseline.mutate(projectId)} loading={createBaseline.isPending}>
                        Approve &amp; freeze baseline
                      </Button>
                      {createBaseline.isError && (
                        <ErrorState
                          message={createBaseline.error instanceof ApiError ? createBaseline.error.message : "Could not create baseline."}
                        />
                      )}
                    </CardContent>
                  </Card>

                  <Section title="Scope changes vs baseline">
                    {changes.isLoading ? (
                      <LoadingState lines={4} />
                    ) : changes.isError ? (
                      <ErrorState message={changes.error instanceof ApiError ? changes.error.message : "Could not load changes."} onRetry={() => changes.refetch()} />
                    ) : (
                      <ScopeChanges summaries={changes.data ?? []} />
                    )}
                  </Section>

                  {baselines.data && baselines.data.some((b) => b.status === "proposed") && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm">Pending baseline updates</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <p className="text-xs text-muted-foreground">
                          Approving an update replaces the baseline. The current baseline stays until you approve.
                        </p>
                        {changes.data?.map((c) =>
                          c.changes.length > 0 ? (
                            <Button
                              key={c.to_transcript_id}
                              size="sm"
                              variant="outline"
                              onClick={() => approveUpdate.mutate({ id: projectId, transcriptId: c.to_transcript_id })}
                              loading={approveUpdate.isPending}
                            >
                              Approve update from {c.to_transcript_id}
                            </Button>
                          ) : null,
                        )}
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}

              {tab === "history" && (
                <Section title="Review & audit history">
                  {events.isLoading ? (
                    <LoadingState lines={5} />
                  ) : events.isError ? (
                    <ErrorState message={events.error instanceof ApiError ? events.error.message : "Could not load events."} onRetry={() => events.refetch()} />
                  ) : (events.data ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">No events recorded.</p>
                  ) : (
                    <ul className="divide-y divide-border rounded-lg border border-border text-sm">
                      {(events.data ?? []).map((e) => (
                        <li key={e.id} className="px-3 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{e.action}</span>
                            <span className="text-xs text-muted-foreground">{e.entity_type}</span>
                            {e.actor && <span className="text-xs text-muted-foreground">by {e.actor}</span>}
                            <span className="ml-auto text-xs text-muted-foreground">{e.at}</span>
                          </div>
                          {e.reason && <p className="mt-0.5 text-xs text-muted-foreground">Reason: {e.reason}</p>}
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <p className="mb-2 text-sm font-semibold">{title}</p>
      {children}
    </div>
  );
}
