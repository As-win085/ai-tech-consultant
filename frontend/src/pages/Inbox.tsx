import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox as InboxIcon, RefreshCw, Settings2, Sparkles, X } from "lucide-react";
import { inboxApi } from "@/api/inbox";
import { ApiError } from "@/api/http";
import { PageHeader } from "@/components/shared/PageHeader";
import { ConnectivityBadge } from "@/components/shared/StatusPills";
import { EmptyState, ErrorState, LoadingState, NoResults } from "@/components/shared/StateViews";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmailList, type InboxFilters } from "@/features/inbox/EmailList";
import { EmailDetail } from "@/features/inbox/EmailDetail";
import type { ReviewActionPayload } from "@/types/inbox";

export function InboxPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<InboxFilters>({
    search: "",
    state: "",
    category: "",
    urgency: "",
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const ready = useQuery({
    queryKey: ["inbox", "ready"],
    queryFn: () => inboxApi.ready(),
    retry: 1,
  });

  const list = useQuery({
    queryKey: ["inbox", "list", { state: filters.state, category: filters.category }],
    queryFn: ({ signal }) => inboxApi.listEmails({ state: filters.state || undefined, category: filters.category || undefined }, signal),
    retry: 1,
  });

  const detail = useQuery({
    queryKey: ["inbox", "item", selectedId],
    queryFn: ({ signal }) => inboxApi.getEmail(selectedId!, signal),
    enabled: Boolean(selectedId),
    retry: 1,
  });

  const draft = useMutation({
    mutationFn: (id: string) => inboxApi.generateDraft(id),
    onSuccess: (item) => {
      queryClient.setQueryData(["inbox", "item", item.id], item);
      queryClient.invalidateQueries({ queryKey: ["inbox", "list"] });
    },
  });

  // Auto-generate draft when an email with no draft is selected
  useEffect(() => {
    if (
      selected &&
      !selected.draft &&
      selected.state === "pending_review" &&
      !draft.isPending
    ) {
      draft.mutate(selected.id);
    }
  }, [selected?.id, selected?.draft, selected?.state]);

  const review = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ReviewActionPayload }) => inboxApi.review(id, payload),
    onSuccess: (result) => {
      queryClient.setQueryData(["inbox", "item", result.item.id], result.item);
      queryClient.invalidateQueries({ queryKey: ["inbox", "list"] });
      queryClient.invalidateQueries({ queryKey: ["inbox", "ready"] });
    },
  });

  const filteredItems = useMemo(() => {
    const items = list.data?.items ?? [];
    const q = filters.search.trim().toLowerCase();
    return items.filter((item) => {
      if (filters.urgency && item.classification.urgency !== filters.urgency) return false;
      if (!q) return true;
      return (
        item.email.subject.toLowerCase().includes(q) ||
        item.email.from.toLowerCase().includes(q)
      );
    });
  }, [list.data, filters.search, filters.urgency]);

  const selected = detail.data ?? null;
  const kbReachable = ready.data?.knowledgeBrain?.reachable;
  const automation = ready.data?.automation;

  const [showSettings, setShowSettings] = useState(false);

  const stats = useQuery({
    queryKey: ["inbox", "stats"],
    queryFn: ({ signal }) => inboxApi.stats(signal),
    enabled: showSettings,
  });

  const hasFilters = Boolean(filters.search || filters.state || filters.category || filters.urgency);

  return (
    <div>
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-start justify-end bg-black/30" onClick={() => setShowSettings(false)}>
          <div className="m-4 w-80 rounded-xl border border-border bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold">Queue settings</h3>
              <Button variant="ghost" size="sm" onClick={() => setShowSettings(false)}><X className="size-4" /></Button>
            </div>
            {stats.isLoading && <p className="text-sm text-muted-foreground">Loading stats…</p>}
            {stats.isError && <p className="text-sm text-destructive">Could not load stats.</p>}
            {stats.data && (
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-xs text-muted-foreground">Total emails</p>
                    <p className="text-xl font-bold">{stats.data.total}</p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-xs text-muted-foreground">Unedited approvals</p>
                    <p className="text-xl font-bold">{stats.data.automation.consecutiveUneditedApprovals}<span className="text-xs text-muted-foreground">/{stats.data.automation.threshold}</span></p>
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">By state</p>
                  <div className="space-y-1">
                    {Object.entries(stats.data.byState).map(([state, count]) => (
                      <div key={state} className="flex justify-between text-xs">
                        <span className="text-muted-foreground">{state.replace(/_/g, " ")}</span>
                        <span className="font-medium">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">By category</p>
                  <div className="space-y-1">
                    {Object.entries(stats.data.byCategory).map(([cat, count]) => (
                      <div key={cat} className="flex justify-between text-xs">
                        <span className="text-muted-foreground">{cat.replace(/_/g, " ")}</span>
                        <span className="font-medium">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Automation eligible: <strong>{stats.data.automation.automationEligible ? "Yes" : "No"}</strong>. A human still approves every reply.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
      <PageHeader
        title="Inbox Agent"
        description="Classify customer emails, ground drafts in Knowledge Brain evidence, and approve, edit, reject, or escalate every reply. No email is ever sent automatically."
        actions={
          <div className="flex items-center gap-2">
            <ConnectivityBadge online={ready.data ? kbReachable !== false : null} label={kbReachable ? "KB reachable" : ready.data ? "KB unreachable" : "Checking…"} />
            <Button variant="outline" size="sm" onClick={() => list.refetch()} disabled={list.isFetching}>
              <RefreshCw className={list.isFetching ? "size-4 animate-spin" : "size-4"} /> Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowSettings(true)}>
              <Settings2 className="size-4" /> Queue settings
            </Button>
          </div>
        }
      />

      {automation && (
        <div className="mb-4 rounded-lg border border-border bg-card px-4 py-2.5 text-sm">
          <span className="text-muted-foreground">Automation safeguard: </span>
          <strong className="tabular-nums">{automation.consecutiveUneditedApprovals}</strong>
          <span className="text-muted-foreground"> consecutive unedited approvals. </span>
          <span className="text-muted-foreground">
            A human still approves every reply; reaching the threshold only sets a policy flag.
          </span>
        </div>
      )}

      {list.isError ? (
        <ErrorState
          title="Could not load the inbox"
          message={
            list.error instanceof ApiError
              ? list.error.message
              : "The Inbox Agent service is unreachable. Start Task 2 on port 8080."
          }
          requestId={list.error instanceof ApiError ? list.error.requestId : undefined}
          onRetry={() => list.refetch()}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
          <Card className="overflow-hidden">
            {list.isLoading ? (
              <div className="p-4">
                <LoadingState lines={5} />
              </div>
            ) : filteredItems.length === 0 ? (
              hasFilters ? (
                <div className="p-4">
                  <NoResults
                    onClear={() =>
                      setFilters({ search: "", state: "", category: "", urgency: "" })
                    }
                  />
                </div>
              ) : (
                <div className="p-4">
                  <EmptyState
                    icon={<InboxIcon className="size-8" />}
                    title="No emails yet"
                    description="Ingest the synthetic dataset by starting Task 2 with EMAIL_DATASET_PATH set."
                  />
                </div>
              )
            ) : (
              <EmailList
                items={filteredItems}
                selectedId={selectedId}
                onSelect={setSelectedId}
                filters={filters}
                onFiltersChange={setFilters}
              />
            )}
          </Card>

          <div>
            {!selectedId ? (
              <EmptyState
                title="Select an email"
                description="Choose an email from the list to review its classification, draft, and citations."
              />
            ) : detail.isLoading ? (
              <Card className="p-6">
                <LoadingState lines={6} />
              </Card>
            ) : detail.isError ? (
              <ErrorState
                title="Could not load this email"
                message={detail.error instanceof ApiError ? detail.error.message : "Not found."}
                onRetry={() => detail.refetch()}
              />
            ) : selected ? (
              <div className="space-y-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => draft.mutate(selected.id)}
                  disabled={draft.isPending || selected.state !== "pending_review"}
                  loading={draft.isPending}
                >
                  <Sparkles className="size-4" />
                  {selected.draft ? "Regenerate draft" : "Generate draft"}
                </Button>
                {draft.isError && (
                  <ErrorState
                    title="Draft generation failed"
                    message={draft.error instanceof ApiError ? draft.error.message : "Unknown error."}
                    onRetry={() => draft.mutate(selected.id)}
                  />
                )}
                <EmailDetail
                  item={selected}
                  onBack={() => setSelectedId(null)}
                  onReview={(payload) => review.mutate({ id: selected.id, payload })}
                  reviewing={review.isPending}
                  result={review.data ?? null}
                />
                {review.isError && (
                  <ErrorState
                    title="Review action failed"
                    message={review.error instanceof ApiError ? review.error.message : "Unknown error."}
                    requestId={review.error instanceof ApiError ? review.error.requestId : undefined}
                  />
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
