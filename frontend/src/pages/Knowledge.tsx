import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import {
  BookOpen,
  ExternalLink,
  GraduationCap,
  HelpCircle,
  Send,
  ShieldAlert,
} from "lucide-react";
import { knowledgeApi } from "@/api/knowledge";
import { ApiError } from "@/api/http";
import { isDemo } from "@/api/config";
import type { AskResponse, Citation } from "@/types/knowledge";
import { PageHeader } from "@/components/shared/PageHeader";
import { EvidenceBadge } from "@/components/shared/StatusPills";
import { ErrorState } from "@/components/shared/StateViews";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const askSchema = z.object({
  question: z
    .string()
    .trim()
    .min(2, "Enter at least two characters.")
    .max(2000, "Question must be under 2000 characters."),
});
type AskForm = z.infer<typeof askSchema>;

interface ConversationTurn {
  id: string;
  question: string;
  response?: AskResponse;
  error?: ApiError;
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <li className="rounded-lg border border-border bg-muted/40 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium leading-snug">{citation.title}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {citation.heading ? `${citation.heading} · ` : ""}
            chunk #{citation.chunk_index} · score {citation.score.toFixed(3)}
          </p>
        </div>
        <EvidenceBadge status="sufficient" className="shrink-0" />
      </div>
      {citation.canonical_url && (
        <a
          href={citation.canonical_url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View source <ExternalLink className="size-3" />
        </a>
      )}
    </li>
  );
}

function AnswerTurn({ turn }: { turn: ConversationTurn }) {
  if (turn.error) {
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium text-muted-foreground">You asked:</p>
        <p className="rounded-md bg-muted px-3 py-2 text-sm italic">{turn.question}</p>
        <ErrorState
          title={turn.error.kind === "timeout" ? "Request timed out" : "Knowledge Brain error"}
          message={turn.error.message}
          requestId={turn.error.requestId}
        />
      </div>
    );
  }

  const r = turn.response!;
  const abstained = r.evidence_status === "insufficient" || r.evidence_status === "conflicting";

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">You asked</p>
        <p className="rounded-md bg-muted px-3 py-2 text-sm italic">{turn.question}</p>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Answer</p>
          <EvidenceBadge status={r.evidence_status} />
          <span className="text-xs text-muted-foreground">
            confidence {r.confidence.level} ({r.confidence.score.toFixed(2)})
          </span>
        </div>
        <div
          className={cn(
            "rounded-lg border p-4 text-sm leading-relaxed",
            abstained ? "border-warning/40 bg-warning/10" : "border-border bg-card",
          )}
        >
          {r.answer}
        </div>
        <p className="text-xs text-muted-foreground">
          {r.model ? `Model: ${r.model} · ` : ""}Basis: {r.confidence.basis}
        </p>
      </div>

      {r.needs_escalation && (
        <Alert variant="warning">
          <ShieldAlert />
          <AlertTitle>Escalation recommended</AlertTitle>
          <AlertDescription>
            {r.escalation_reason ?? "The agent recommends human review before answering."}
            {r.escalation_id && (
              <span className="mt-1 block text-xs">Escalation ID: {r.escalation_id}</span>
            )}
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <BookOpen className="size-3.5" /> Citations ({r.citations.length})
        </p>
        {r.citations.length === 0 ? (
          <p className="rounded-md border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
            No citations returned. The agent did not find enough supporting evidence to cite.
          </p>
        ) : (
          <ul className="space-y-2">
            {r.citations.map((c) => (
              <CitationCard key={c.chunk_id} citation={c} />
            ))}
          </ul>
        )}
      </div>

      {r.retrieved_chunks && r.retrieved_chunks.length > 0 && (
        <details className="rounded-lg border border-border">
          <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-muted-foreground">
            Retrieved evidence chunks ({r.retrieved_chunks.length}) — diagnostics
          </summary>
          <div className="space-y-3 border-t border-border p-4">
            {r.retrieved_chunks.map((chunk) => (
              <div key={chunk.chunk_id} className="text-xs">
                <p className="font-medium">
                  {chunk.title} · score {chunk.score.toFixed(3)}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{chunk.content}</p>
              </div>
            ))}
          </div>
        </details>
      )}

      <p className="text-[11px] text-muted-foreground">Request ID: {r.request_id}</p>
    </div>
  );
}

export function KnowledgePage() {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  const form = useForm<AskForm>({ resolver: zodResolver(askSchema), defaultValues: { question: "" } });

  const mutation = useMutation({
    mutationFn: (question: string) => knowledgeApi.ask({ question }),
    onSuccess: (response, question) => {
      setTurns((prev) => [...prev, { id: crypto.randomUUID(), question, response }]);
      form.reset({ question: "" });
      requestAnimationFrame(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }));
    },
    onError: (error, question) => {
      setTurns((prev) => [
        ...prev,
        { id: crypto.randomUUID(), question, error: error instanceof ApiError ? error : new ApiError({ kind: "unknown", message: String(error) }) },
      ]);
      requestAnimationFrame(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }));
    },
  });

  const onSubmit = form.handleSubmit(({ question }) => {
    mutation.mutate(question.trim());
  });

  return (
    <div>
      <PageHeader
        title="Knowledge Brain"
        description="Ask a question about the Brilliant Directories support knowledge base. Answers are grounded in retrieved articles, with verifiable citations, or a safe abstention when evidence is insufficient."
        actions={
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <GraduationCap className="size-4" />
            Human-in-the-loop · no fabricated sources
          </div>
        }
      />

      {isDemo && (
        <Alert variant="info" className="mb-4">
          <HelpCircle />
          <AlertTitle>Demo mode enabled</AlertTitle>
          <AlertDescription>Responses are served from demo fixtures, not a live model.</AlertDescription>
        </Alert>
      )}

      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Ask a question</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="question" className="sr-only">
                Your question
              </Label>
              <Input
                id="question"
                placeholder="e.g. How do I reset a member's password?"
                disabled={mutation.isPending}
                aria-invalid={form.formState.errors.question ? true : undefined}
                {...form.register("question")}
              />
              {form.formState.errors.question && (
                <p className="text-xs text-destructive" role="alert">
                  {form.formState.errors.question.message}
                </p>
              )}
            </div>
            <Button type="submit" loading={mutation.isPending} className="sm:w-auto">
              <Send className="size-4" /> Ask
            </Button>
          </form>
        </CardContent>
      </Card>

      <div ref={listRef} className="space-y-6">
        {turns.length === 0 && !mutation.isPending && (
          <div className="rounded-lg border border-dashed border-border px-6 py-12 text-center text-sm text-muted-foreground">
            <HelpCircle className="mx-auto mb-2 size-8" />
            Ask a question to see a grounded answer with citations.
          </div>
        )}

        {turns.map((turn) => (
          <Card key={turn.id}>
            <CardContent className="pt-6">
              <AnswerTurn turn={turn} />
            </CardContent>
          </Card>
        ))}

        {mutation.isPending && (
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-2" role="status" aria-live="polite">
                <div className="h-3 w-1/4 animate-pulse rounded bg-muted" />
                <div className="h-3 w-full animate-pulse rounded bg-muted" />
                <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
                <p className="pt-1 text-xs text-muted-foreground">
                  Retrieving evidence and generating an answer… this can take a while for local models.
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
