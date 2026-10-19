import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Compact status pill used across the workspace (requirement states, sync
 * states, review-queue badges, etc.). Styles mirror the enterprise design
 * spec: small bold text, subtle tinted backgrounds, light borders.
 */
const tagVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded px-2 py-0.5 text-[10px] font-bold",
  {
    variants: {
      variant: {
        // Indigo tint — AI-generated / needs review
        indigo: "bg-indigo-100 text-indigo-800",
        "indigo-soft": "bg-indigo-50 text-indigo-700",
        // Emerald tint — reviewed / synced
        emerald: "bg-emerald-100 text-emerald-800",
        "emerald-soft": "bg-emerald-50 text-emerald-700",
        // Amber tint — needs clarification / partial / escalated
        amber: "bg-amber-100 text-amber-800",
        "amber-soft": "bg-amber-50 text-amber-700",
        // Rose tint — failed / unverified
        rose: "bg-rose-100 text-rose-900",
        // Slate tint — neutral
        slate: "bg-slate-100 text-slate-600",
        "slate-soft": "bg-slate-50 text-slate-500",
      },
      size: {
        sm: "px-2 py-0.5 text-[10px]",
        md: "px-2.5 py-0.5 text-xs",
      },
      shape: {
        rounded: "rounded",
        pill: "rounded-full",
      },
    },
    defaultVariants: {
      variant: "slate",
      size: "sm",
      shape: "rounded",
    },
  },
);

export interface TagProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof tagVariants> {}

export function Tag({ className, variant, size, shape, ...props }: TagProps) {
  return <span className={cn(tagVariants({ variant, size, shape }), className)} {...props} />;
}

/** Common named states used across views, kept consistent in one place. */
export const TAG_STYLES = {
  reviewed: "emerald",
  aiSuggestion: "indigo",
  needsClarification: "amber",
  needsReview: "indigo-soft",
  escalated: "amber",
  missingEvidence: "amber-soft",
  synced: "emerald",
  partialSync: "amber",
  failed: "rose",
  draft: "indigo-soft",
  neutral: "slate",
} as const satisfies Record<string, NonNullable<TagProps["variant"]>>;
