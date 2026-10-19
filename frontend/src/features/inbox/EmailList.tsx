import { Badge } from "@/components/ui/badge";
import { ReviewStateBadge, UrgencyBadge } from "@/components/shared/StatusPills";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { CATEGORIES, REVIEW_STATES, URGENCIES } from "@/types/inbox";
import type { InboxItem } from "@/types/inbox";
import { cn } from "@/lib/utils";

export interface InboxFilters {
  search: string;
  state: string;
  category: string;
  urgency: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  product_howto: "How-to",
  troubleshooting: "Troubleshooting",
  billing_account: "Billing / account",
  feature_request: "Feature request",
  complaint: "Complaint",
  unsupported_unclear: "Unsupported / unclear",
};

export function EmailList({
  items,
  selectedId,
  onSelect,
  filters,
  onFiltersChange,
}: {
  items: InboxItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filters: InboxFilters;
  onFiltersChange: (next: InboxFilters) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b border-border p-3">
        <div className="relative">
          <SearchInput value={filters.search} onChange={(v) => onFiltersChange({ ...filters, search: v })} />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Select
            aria-label="Filter by state"
            value={filters.state}
            onChange={(e) => onFiltersChange({ ...filters, state: e.target.value })}
          >
            <option value="">All states</option>
            {REVIEW_STATES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filter by category"
            value={filters.category}
            onChange={(e) => onFiltersChange({ ...filters, category: e.target.value })}
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c] ?? c}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filter by urgency"
            value={filters.urgency}
            onChange={(e) => onFiltersChange({ ...filters, urgency: e.target.value })}
          >
            <option value="">All urgency</option>
            {URGENCIES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </Select>
        </div>
        {(filters.search || filters.state || filters.category || filters.urgency) && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={() => onFiltersChange({ search: "", state: "", category: "", urgency: "" })}
          >
            Clear filters
          </Button>
        )}
      </div>

      <ul className="flex-1 divide-y divide-border overflow-y-auto scrollbar-thin">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              className={cn(
                "w-full px-3 py-3 text-left transition-colors hover:bg-accent",
                selectedId === item.id && "bg-primary/10",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-medium">{item.email.subject}</p>
                <ReviewStateBadge state={item.state} className="shrink-0" />
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.email.from}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Badge variant="secondary">{CATEGORY_LABELS[item.classification.category] ?? item.classification.category}</Badge>
                <UrgencyBadge urgency={item.classification.urgency} />
                {item.classification.needsEscalation && (
                  <Badge variant="warning">Escalate</Badge>
                )}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SearchInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Input
      aria-label="Search emails"
      placeholder="Search sender or subject…"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
