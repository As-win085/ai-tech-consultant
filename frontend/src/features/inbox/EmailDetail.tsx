import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  ExternalLink,
  FileEdit,
  MessageSquare,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ReviewStateBadge, UrgencyBadge } from "@/components/shared/StatusPills";
import { formatTimestamp } from "@/lib/utils";
import type {
  Citation,
  InboxItem,
  ReviewActionPayload,
  ReviewResultResponse,
} from "@/types/inbox";

const CATEGORY_LABELS: Record<string, string> = {
  product_howto: "How-to",
  troubleshooting: "Troubleshooting",
  billing_account: "Billing / account",
  feature_request: "Feature request",
  complaint: "Complaint",
  unsupported_unclear: "Unsupported / unclear",
};

const reviewSchema = z.object({
  editedDraft: z.string().max(20000).optional(),
  rejectionReason: z.string().max(2000).optional(),
  escalationReason: z.string().max(2000).optional(),
  feedback: z.string().max(2000).optional(),
  reviewerId: z.string().max(200).optional(),
});

type ReviewForm = z.infer<typeof reviewSchema>;

function MiniCitation({ c }: { c: Citation }) {
  return (
    <li className="rounded border border-border bg-muted/40 px-2 py-1 text-xs">
      <span className="font-medium">{c.title ?? c.chunk_id}</span>
      {c.canonical_url && (
        <a
          href={c.canonical_url}
          target="_blank"
          rel="noreferrer"
          className="ml-1 inline-flex items-center gap-0.5 text-primary hover:underline"
        >
          source <ExternalLink className="size-2.5" />
        </a>
      )}
    </li>
  );
}

export function EmailDetail({
  item,
  onBack,
  onReview,
  reviewing,
  result,
}: {
  item: InboxItem;
  onBack: () => void;
  onReview: (payload: ReviewActionPayload) => void;
  reviewing: boolean;
  result: ReviewResultResponse | null;
}) {
  const draft = item.draft;
  const terminal = item.state !== "pending_review";
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [action, setAction] = useState<ReviewActionPayload["action"] | null>(null);

  const form = useForm<ReviewForm>({
    resolver: zodResolver(reviewSchema),
    defaultValues: { editedDraft: draft?.body ?? "" },
  });

  useEffect(() => {
    form.reset({ editedDraft: item.draft?.body ?? "" });
    setMode("view");
    setAction(null);
  }, [item.id, item.draft?.body, item.state, form]);

  const submit = (kind: ReviewActionPayload["action"]) => {
    const values = form.getValues();
    const payload: ReviewActionPayload = {
      action: kind,
      reviewerId: values.reviewerId?.trim() || undefined,
      feedback: values.feedback?.trim() || undefined,
    };
    if (kind === "edit") {
      payload.editedDraft = values.editedDraft ?? "";
    }
    if (kind === "reject") {
      payload.rejectionReason = values.rejectionReason?.trim() || "Rejected by reviewer";
    }
    if (kind === "escalate") {
      payload.escalationReason = values.escalationReason?.trim() || "Escalated by reviewer";
    }
    setAction(kind);
    onReview(payload);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Button variant="ghost" size="sm" onClick={onBack} className="lg:hidden">
          <ArrowLeft className="size-4" /> Back
        </Button>
        <div className="flex items-center gap-2">
          <ReviewStateBadge state={item.state} />
          <span className="text-xs text-muted-foreground">
            Updated {formatTimestamp(item.updatedAt)}
          </span>
        </div>
      </div>

      {/* Original email */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{item.email.subject}</CardTitle>
          <p className="text-xs text-muted-foreground">
            From {item.email.from} · received {formatTimestamp(item.email.receivedAt)}
          </p>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap rounded-md bg-muted p-3 text-sm leading-relaxed">
            {item.email.body}
          </p>
        </CardContent>
      </Card>

      {/* Classification */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Bot className="size-4 text-primary" /> Classification
            {item.classification.fallback && <Badge variant="warning">fallback</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{CATEGORY_LABELS[item.classification.category] ?? item.classification.category}</Badge>
            <UrgencyBadge urgency={item.classification.urgency} />
            <Badge variant="outline">ambiguity: {item.classification.ambiguity}</Badge>
            <Badge variant="outline">confidence {(item.classification.confidence * 100).toFixed(0)}%</Badge>
            {item.classification.needsEscalation && <Badge variant="warning">needs escalation</Badge>}
          </div>
          {item.classification.riskFlags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {item.classification.riskFlags.map((f) => (
                <Badge key={f} variant="destructive">
                  {f.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          )}
          {item.classification.reasoning && (
            <p className="text-xs text-muted-foreground">Reasoning: {item.classification.reasoning}</p>
          )}
        </CardContent>
      </Card>

      {/* Draft + review */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Response draft</CardTitle>
            {draft && (
              <div className="flex gap-1 text-xs">
                <Button
                  variant={mode === "view" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setMode("view")}
                >
                  View
                </Button>
                <Button
                  variant={mode === "edit" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setMode("edit")}
                  disabled={terminal}
                >
                  <FileEdit className="size-3.5" /> Edit
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!draft ? (
            <p className="rounded-md border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
              No draft yet. A draft is produced by the Knowledge Brain integration.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant={draft.grounded ? "success" : "warning"}>
                  {draft.grounded ? "Grounded in citations" : "Not grounded (clarify/escalate)"}
                </Badge>
                {draft.kbEvidenceStatus && (
                  <Badge variant="outline">KB evidence: {draft.kbEvidenceStatus}</Badge>
                )}
                {draft.grounded && <CheckCircle2 className="size-3.5 text-success" />}
              </div>

              {mode === "edit" ? (
                <div className="space-y-1.5">
                  <Label htmlFor="editedDraft">Edited draft (this becomes the approved body)</Label>
                  <Textarea
                    id="editedDraft"
                    rows={10}
                    {...form.register("editedDraft")}
                    className="font-mono text-sm"
                  />
                </div>
              ) : (
                <div className="whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 text-sm leading-relaxed">
                  {draft.body}
                </div>
              )}

              {draft.confirmedFacts.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Confirmed facts (source-grounded)
                  </p>
                  <ul className="list-disc space-y-1 pl-5 text-xs">
                    {draft.confirmedFacts.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}
              {draft.assumptions.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-warning-foreground">
                    Assumptions (not verified)
                  </p>
                  <ul className="list-disc space-y-1 pl-5 text-xs">
                    {draft.assumptions.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}
              {draft.escalationReason && (
                <Alert variant="warning">
                  <ShieldAlert />
                  <AlertTitle>Draft escalation reason</AlertTitle>
                  <AlertDescription>{draft.escalationReason}</AlertDescription>
                </Alert>
              )}
              {draft.citations.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Reviewer citations ({draft.citations.length})
                  </p>
                  <ul className="space-y-1">
                    {draft.citations.map((c) => (
                      <MiniCitation key={c.chunk_id} c={c} />
                    ))}
                  </ul>
                </div>
              )}
              {draft.kbRequestId && (
                <p className="text-[11px] text-muted-foreground">KB request: {draft.kbRequestId}</p>
              )}
            </>
          )}

          {item.automationExcluded && (
            <Alert variant="info">
              <ShieldAlert />
              <AlertTitle>Excluded from automation eligibility</AlertTitle>
              <AlertDescription>
                {item.automationExclusionReasons.join("; ") || "Configured safety exclusion."}
              </AlertDescription>
            </Alert>
          )}

          {result && action && (
            <Alert variant="success">
              <CheckCircle2 />
              <AlertTitle>Review recorded</AlertTitle>
              <AlertDescription>
                Action “{action}” recorded. Consecutive unedited approvals:{" "}
                {result.automation.consecutiveUneditedApprovals}
                {(result.automation as { threshold?: number }).threshold !== undefined
                  ? `/${(result.automation as { threshold?: number }).threshold}`
                  : ""}.
                {result.automation.automationEligible && " Automation eligible — a human still approves every reply."}
              </AlertDescription>
            </Alert>
          )}

          {/* Review controls */}
          {!terminal && draft && (
            <div className="space-y-3 border-t border-border pt-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="reviewerId">Reviewer ID (optional)</Label>
                  <Input id="reviewerId" placeholder="e.g. reviewer-1" {...form.register("reviewerId")} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="feedback">Feedback (optional)</Label>
                  <Input id="feedback" placeholder="Why approve/edit/reject" {...form.register("feedback")} />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rejectionReason">Rejection reason (used when rejecting)</Label>
                <Input id="rejectionReason" placeholder="Reason" {...form.register("rejectionReason")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="escalationReason">Escalation reason (used when escalating)</Label>
                <Input id="escalationReason" placeholder="Reason" {...form.register("escalationReason")} />
              </div>
              <p className="text-xs text-muted-foreground">
                Approving never sends an email — it only marks the draft ready for a human to send.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="success" onClick={() => submit("approve")} loading={reviewing}>
                  <CheckCircle2 className="size-4" /> Approve
                </Button>
                <Button variant="default" onClick={() => submit("edit")} loading={reviewing}>
                  <FileEdit className="size-4" /> Save edit
                </Button>
                <Button variant="destructive" onClick={() => submit("reject")} loading={reviewing}>
                  <XCircle className="size-4" /> Reject
                </Button>
                <Button variant="outline" onClick={() => submit("escalate")} loading={reviewing}>
                  <ShieldAlert className="size-4" /> Escalate
                </Button>
              </div>
            </div>
          )}

          {item.reviewHistory.length > 0 && (
            <div className="border-t border-border pt-3">
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <MessageSquare className="size-3.5" /> Review history
              </p>
              <ul className="space-y-1.5 text-xs">
                {item.reviewHistory.map((h, i) => (
                  <li key={i} className="rounded border border-border px-2 py-1.5">
                    <span className="font-medium">{h.action}</span> · {h.fromState} → {h.toState} ·{" "}
                    {formatTimestamp(h.at)}
                    {h.reviewerId && <span className="text-muted-foreground"> · by {h.reviewerId}</span>}
                    {h.edited && <Badge variant="info" className="ml-1">edited</Badge>}
                    {h.rejectionReason && <p className="mt-0.5 text-muted-foreground">Reason: {h.rejectionReason}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
