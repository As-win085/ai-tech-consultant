import { AlertTriangle, Inbox, RefreshCw, SearchX } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Loading skeleton block used while a query is in flight. */
export function LoadingState({ label = "Loading…", lines = 3 }: { label?: string; lines?: number }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
    </div>
  );
}

/** Empty-state panel for when a list has no items. */
export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className,
      )}
    >
      <div className="mb-3 text-muted-foreground">{icon ?? <Inbox className="size-8" />}</div>
      <p className="font-medium">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Actionable error panel. Renders retry when the caller supplies one. */
export function ErrorState({
  title = "Something went wrong",
  message,
  requestId,
  onRetry,
  icon,
  className,
}: {
  title?: string;
  message: string;
  requestId?: string;
  onRetry?: () => void;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <Alert variant="destructive" className={cn("bg-destructive/10", className)}>
      {icon ?? <AlertTriangle />}
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{message}</p>
        {requestId && (
          <p className="text-xs text-muted-foreground">
            Request ID: <code className="font-mono">{requestId}</code>
          </p>
        )}
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} className="mt-1">
            <RefreshCw className="size-3.5" /> Retry
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

/** Search-specific empty state. */
export function NoResults({ onClear }: { onClear?: () => void }) {
  return (
    <EmptyState
      icon={<SearchX className="size-8" />}
      title="No matching results"
      description="Try adjusting your filters or search terms."
      action={
        onClear && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear filters
          </Button>
        )
      }
    />
  );
}
