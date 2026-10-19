import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Brain, CalendarRange, Inbox, Radio } from "lucide-react";
import { Link } from "react-router-dom";
import { knowledgeApi } from "@/api/knowledge";
import { inboxApi } from "@/api/inbox";
import { meetingApi } from "@/api/meeting";
import { config } from "@/api/config";
import { ApiError } from "@/api/http";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConnectivityBadge } from "@/components/shared/StatusPills";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/StateViews";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function useServiceHealth(name: string, readyFn: () => Promise<unknown>) {
  return useQuery({
    queryKey: ["health", name],
    queryFn: async () => {
      // Probe health (never throws), then attempt /ready for dependency detail.
      const online = await (name === "knowledge"
        ? knowledgeApi.probe()
        : name === "inbox"
          ? inboxApi.probe()
          : meetingApi.probe());
      if (!online) return { online: false as const, ready: null as unknown, error: null as string | null };
      try {
        const ready = await readyFn();
        return { online: true as const, ready, error: null as string | null };
      } catch (err) {
        const message = err instanceof ApiError ? err.message : String(err);
        return { online: true as const, ready: null as unknown, error: message };
      }
    },
    retry: 1,
    staleTime: 10_000,
  });
}

function MetricTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function OverviewPage() {
  const knowledge = useServiceHealth("knowledge", () => knowledgeApi.ready());
  const inbox = useServiceHealth("inbox", () => inboxApi.ready());
  const meeting = useServiceHealth("meeting", () => meetingApi.ready());

  const inboxStats = useQuery({
    queryKey: ["overview", "inbox-stats"],
    queryFn: () => inboxApi.stats(),
    enabled: inbox.data?.online === true,
    retry: 1,
  });

  const meetingProjects = useQuery({
    queryKey: ["overview", "meeting-projects"],
    queryFn: () => meetingApi.listProjects(),
    enabled: meeting.data?.online === true,
    retry: 1,
  });

  const allOnline = [knowledge.data?.online, inbox.data?.online, meeting.data?.online];
  const anyChecking =
    knowledge.isLoading || inbox.isLoading || meeting.isLoading;

  const knowledgeIndex = (knowledge.data?.ready as { index?: Record<string, unknown> } | null)?.index;
  const indexedDocuments =
    knowledgeIndex && typeof knowledgeIndex["document_count"] === "number"
      ? (knowledgeIndex["document_count"] as number)
      : knowledgeIndex && typeof knowledgeIndex["chunks"] === "number"
        ? (knowledgeIndex["chunks"] as number)
        : null;

  const byState = inboxStats.data?.byState ?? {};
  const pendingReview = byState["pending_review"] ?? 0;
  const approved = (byState["approved"] ?? 0) + (byState["edited_and_approved"] ?? 0);
  const rejected = byState["rejected"] ?? 0;
  const escalated = byState["escalated"] ?? 0;

  const projects = meetingProjects.data?.projects ?? [];

  const automation = inboxStats.data?.automation;

  return (
    <div>
      <PageHeader
        title="Operations Overview"
        description="Live connectivity and workload metrics read directly from the three agent backends. Values show an explicit unavailable state when a service cannot be reached."
        actions={
          <Button variant="outline" size="sm" asChild>
            <a href={`${config.knowledgeUrl}/docs`} target="_blank" rel="noreferrer">
              API docs
            </a>
          </Button>
        }
      />

      {/* Service connectivity */}
      <div className="mb-6 grid gap-4 md:grid-cols-3">
        <ServiceCard
          title="Knowledge Brain"
          icon={<Brain className="size-5" />}
          to="/knowledge"
          query={knowledge}
          detail={
            knowledge.data?.ready
              ? `Readiness: ${(knowledge.data.ready as { status?: string }).status ?? "unknown"}`
              : knowledge.data?.error
          }
        />
        <ServiceCard
          title="Inbox Agent"
          icon={<Inbox className="size-5" />}
          to="/inbox"
          query={inbox}
          detail={
            inbox.data?.ready
              ? `KB reachable: ${String((inbox.data.ready as { knowledgeBrain?: { reachable: boolean } }).knowledgeBrain?.reachable ?? false)}`
              : inbox.data?.error
          }
        />
        <ServiceCard
          title="Meeting-to-Scope"
          icon={<CalendarRange className="size-5" />}
          to="/meeting"
          query={meeting}
          detail={
            meeting.data?.ready
              ? `KB reachable: ${String((meeting.data.ready as { knowledge_brain_reachable?: boolean }).knowledge_brain_reachable ?? false)}`
              : meeting.data?.error
          }
        />
      </div>

      {/* Metrics */}
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Radio className="size-4 text-primary" /> Workload metrics
      </div>
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          label="Indexed chunks"
          value={
            anyChecking && knowledge.isLoading ? (
              <LoadingState lines={1} />
            ) : indexedDocuments !== null ? (
              indexedDocuments
            ) : (
              <span className="text-base text-muted-foreground">Unavailable</span>
            )
          }
          sub={
            knowledge.data?.online
              ? "From Knowledge Brain /ready index"
              : knowledge.data?.online === false
                ? "Knowledge Brain offline"
                : undefined
          }
        />
        <MetricTile
          label="Awaiting review"
          value={
            inboxStats.isLoading ? (
              <LoadingState lines={1} />
            ) : inboxStats.isError ? (
              <span className="text-base text-muted-foreground">Unavailable</span>
            ) : (
              pendingReview
            )
          }
          sub="Emails pending human review"
        />
        <MetricTile
          label="Approved drafts"
          value={
            inboxStats.isError ? (
              <span className="text-base text-muted-foreground">Unavailable</span>
            ) : (
              approved
            )
          }
          sub={`${rejected} rejected · ${escalated} escalated`}
        />
        <MetricTile
          label="Meeting projects"
          value={
            meetingProjects.isLoading ? (
              <LoadingState lines={1} />
            ) : meetingProjects.isError ? (
              <span className="text-base text-muted-foreground">Unavailable</span>
            ) : (
              projects.length
            )
          }
          sub="Ingested meeting-to-scope projects"
        />
      </div>

      {/* Automation safeguard */}
      <SectionCard title="Automation safeguard">
        {inboxStats.isError ? (
          <p className="text-sm text-muted-foreground">
            Automation state unavailable — Inbox Agent offline.
          </p>
        ) : automation ? (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <span>
              Consecutive unedited approvals:{" "}
              <strong className="tabular-nums">{automation.consecutiveUneditedApprovals}</strong> /{" "}
              {automation.threshold}
            </span>
            <ConnectivityBadge
              online={automation.automationEligible}
              label={automation.automationEligible ? "Eligible (not auto-sending)" : "Below threshold"}
            />
            <p className="w-full text-xs text-muted-foreground">
              Reaching the threshold only sets a policy flag. A human still approves every reply; no
              email is ever sent automatically.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
      </SectionCard>

      {/* Projects list */}
      <SectionCard title="Meeting projects">
        {meetingProjects.isError ? (
          <ErrorState
            title="Meeting service unavailable"
            message={
              meetingProjects.error instanceof ApiError
                ? meetingProjects.error.message
                : "Could not load projects."
            }
            onRetry={() => meetingProjects.refetch()}
          />
        ) : projects.length === 0 ? (
          <EmptyState
            title="No meeting projects yet"
            description="Ingest a transcript from the Meeting-to-Scope page to create one."
            icon={<CalendarRange className="size-8" />}
            action={
              <Button asChild variant="outline" size="sm">
                <Link to="/meeting">Go to Meeting-to-Scope</Link>
              </Button>
            }
          />
        ) : (
          <ul className="divide-y divide-border">
            {projects.slice(0, 6).map((p, i) => (
              <li key={String(p["project_id"] ?? i)} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium">{String(p["project_id"])}</span>
                <span className="text-muted-foreground">
                  {typeof p["transcript_count"] === "number" ? `${p["transcript_count"]} transcripts` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {allOnline.every((v) => v === false) && (
        <EmptyState
          icon={<AlertTriangle className="size-8 text-warning" />}
          title="No backends reachable"
          description="Start Task 1 (port 8000), Task 2 (port 8080), and Task 3 (port 8090), then reload. See the Settings page for connection URLs."
          action={
            <Button asChild variant="outline" size="sm">
              <Link to="/settings">Open settings</Link>
            </Button>
          }
        />
      )}
    </div>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="mb-6">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function ServiceCard({
  title,
  icon,
  to,
  query,
  detail,
}: {
  title: string;
  icon: React.ReactNode;
  to: string;
  query: ReturnType<typeof useServiceHealth>;
  detail?: string | null;
}) {
  const online = query.data?.online ?? null;
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <span className="text-primary">{icon}</span>
            {title}
          </CardTitle>
          <ConnectivityBadge online={online} />
        </div>
        <CardDescription className="line-clamp-2">
          {query.isLoading
            ? "Checking connectivity…"
            : online === false
              ? "Service unreachable"
              : (detail ?? "Reachable")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild variant="ghost" size="sm" className="px-0 text-primary">
          <Link to={to}>Open workspace →</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
