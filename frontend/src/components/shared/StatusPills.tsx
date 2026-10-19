import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "outline" | "success" | "warning" | "destructive" | "info";

const evidenceVariant: Record<string, Variant> = {
  sufficient: "success",
  insufficient: "warning",
  conflicting: "warning",
  unavailable: "destructive",
};

export function EvidenceBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge variant={evidenceVariant[status] ?? "secondary"} className={cn(className)}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

const reviewStateVariant: Record<string, Variant> = {
  pending_review: "info",
  approved: "success",
  edited_and_approved: "success",
  rejected: "destructive",
  escalated: "warning",
};

export function ReviewStateBadge({ state, className }: { state: string; className?: string }) {
  return (
    <Badge variant={reviewStateVariant[state] ?? "secondary"} className={cn(className)}>
      {state.replace(/_/g, " ")}
    </Badge>
  );
}

const urgencyVariant: Record<string, Variant> = {
  low: "secondary",
  medium: "info",
  high: "warning",
  urgent: "destructive",
};

export function UrgencyBadge({ urgency, className }: { urgency: string; className?: string }) {
  return (
    <Badge variant={urgencyVariant[urgency] ?? "secondary"} className={cn(className)}>
      {urgency}
    </Badge>
  );
}

const feasibilityVariant: Record<string, Variant> = {
  supported_by_knowledge: "success",
  potentially_feasible_needs_validation: "info",
  not_supported_by_available_evidence: "warning",
  conflicting_evidence: "warning",
  requires_customer_clarification: "info",
  assessment_unavailable: "destructive",
  not_assessed: "secondary",
};

export function FeasibilityBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge variant={feasibilityVariant[status] ?? "secondary"} className={cn(className)}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

const changeTypeVariant: Record<string, Variant> = {
  added: "success",
  removed: "destructive",
  modified: "warning",
  clarified: "info",
  unresolved: "warning",
  unchanged: "secondary",
};

export function ChangeTypeBadge({ type, className }: { type: string; className?: string }) {
  return (
    <Badge variant={changeTypeVariant[type] ?? "secondary"} className={cn(className)}>
      {type}
    </Badge>
  );
}

/** A connectivity pill that distinguishes online/offline probing results. */
export function ConnectivityBadge({ online, label }: { online: boolean | null; label?: string }) {
  if (online === null) {
    return (
      <Badge variant="secondary" className="gap-1.5">
        <span className="size-1.5 rounded-full bg-muted-foreground" />
        Checking…
      </Badge>
    );
  }
  return (
    <Badge variant={online ? "success" : "destructive"} className="gap-1.5">
      <span className={cn("size-1.5 rounded-full", online ? "bg-success" : "bg-destructive")} />
      {label ?? (online ? "Online" : "Offline")}
    </Badge>
  );
}
