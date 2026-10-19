import { useQuery } from "@tanstack/react-query";
import { ExternalLink, KeyRound, Plug, ShieldCheck } from "lucide-react";
import { knowledgeApi } from "@/api/knowledge";
import { inboxApi } from "@/api/inbox";
import { meetingApi } from "@/api/meeting";
import { config, isDemo } from "@/api/config";
import { PageHeader, Section } from "@/components/shared/PageHeader";
import { ConnectivityBadge } from "@/components/shared/StatusPills";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";

function useProbe(key: string, fn: () => Promise<boolean>) {
  return useQuery({ queryKey: ["settings-probe", key], queryFn: fn, retry: 1, staleTime: 5000 });
}

function ServiceRow({
  name,
  url,
  docsUrl,
  online,
}: {
  name: string;
  url: string;
  docsUrl: string;
  online: boolean | null;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
      <div>
        <p className="text-sm font-medium">{name}</p>
        <p className="text-xs text-muted-foreground">{url}</p>
      </div>
      <div className="flex items-center gap-2">
        <ConnectivityBadge online={online} />
        <a
          href={docsUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          Docs <ExternalLink className="size-3" />
        </a>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const k = useProbe("knowledge", () => knowledgeApi.probe());
  const i = useProbe("inbox", () => inboxApi.probe());
  const m = useProbe("meeting", () => meetingApi.probe());

  const toOnline = (q: ReturnType<typeof useProbe>): boolean | null =>
    q.isLoading ? null : q.data ?? false;

  return (
    <div>
      <PageHeader
        title="Settings & Connection Status"
        description="Service endpoints are read from VITE_* environment variables at build time. No secrets belong in the frontend — each backend holds its own provider keys."
      />

      {isDemo && (
        <Alert variant="info" className="mb-4">
          <ShieldCheck />
          <AlertTitle>Demo mode is ON</AlertTitle>
          <AlertDescription>
            `VITE_DEMO_MODE` is enabled. Pages may serve fixture data instead of live services. Disable it and rebuild to force real API calls.
          </AlertDescription>
        </Alert>
      )}

      <Section title="Service connectivity">
        <Card>
          <CardContent className="divide-y divide-border px-0">
            <ServiceRow name="Knowledge Brain (Task 1)" url={config.knowledgeUrl} docsUrl={`${config.knowledgeUrl}/docs`} online={toOnline(k)} />
            <ServiceRow name="Inbox Agent (Task 2)" url={config.inboxUrl} docsUrl={`${config.inboxUrl}/`} online={toOnline(i)} />
            <ServiceRow name="Meeting-to-Scope (Task 3)" url={config.meetingUrl} docsUrl={`${config.meetingUrl}/docs`} online={toOnline(m)} />
          </CardContent>
        </Card>
      </Section>

      <Section title="Environment variables">
        <Card>
          <CardContent className="space-y-2 pt-6 text-sm">
            <EnvRow name="VITE_KNOWLEDGE_API_URL" value={config.knowledgeUrl} />
            <EnvRow name="VITE_INBOX_API_URL" value={config.inboxUrl} />
            <EnvRow name="VITE_MEETING_API_URL" value={config.meetingUrl} />
            <EnvRow name="VITE_DEMO_MODE" value={isDemo ? "true" : "false"} />
          </CardContent>
        </Card>
      </Section>

      <Section title="Security notes">
        <Card>
          <CardContent className="space-y-3 pt-6 text-sm text-muted-foreground">
            <p className="flex items-start gap-2">
              <KeyRound className="mt-0.5 size-4 shrink-0 text-warning" />
              Provider API keys (Anthropic/OpenAI/Ollama) and database credentials live only on the backends. The frontend bundles no secrets; `VITE_*` values are public by design.
            </p>
            <p className="flex items-start gap-2">
              <Plug className="mt-0.5 size-4 shrink-0 text-info" />
              Review and approval actions are not identity-authenticated by the backends. These endpoints are for a trusted local demo only, not internet-facing deployment.
            </p>
            <p className="flex items-start gap-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" />
              Approving a draft or a baseline never sends email or commits contractually — a human remains the final actor on every outbound action.
            </p>
          </CardContent>
        </Card>
      </Section>
    </div>
  );
}

function EnvRow({ name, value }: { name: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded border border-border px-3 py-2">
      <code className="font-mono text-xs">{name}</code>
      <code className="font-mono text-xs text-muted-foreground">{value}</code>
    </div>
  );
}
