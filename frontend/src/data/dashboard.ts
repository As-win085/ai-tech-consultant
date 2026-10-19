import type { LucideIcon } from "lucide-react";
import { Flag, Layers, Mail, AlertTriangle } from "lucide-react";

export interface Metric {
  label: string;
  value: string;
  sub: string;
  subTone?: "default" | "amber";
  icon: LucideIcon;
  iconTone: "indigo" | "amber" | "rose";
}

export const METRICS: Metric[] = [
  {
    label: "Email drafts",
    value: "3",
    sub: "Awaiting human review",
    icon: Mail,
    iconTone: "indigo",
  },
  {
    label: "Draft scopes",
    value: "2",
    sub: "Ready for requirement review",
    icon: Layers,
    iconTone: "indigo",
  },
  {
    label: "Open escalations",
    value: "2",
    sub: "Need subject-matter input",
    subTone: "amber",
    icon: Flag,
    iconTone: "amber",
  },
  {
    label: "Source issues",
    value: "1",
    sub: "Partial sync · 2 pages excluded",
    icon: AlertTriangle,
    iconTone: "rose",
  },
];

export interface AttentionItem {
  id: string;
  icon: LucideIcon;
  iconTone: "indigo" | "amber";
  title: string;
  meta: string;
  time: string;
  badge: { label: string; tone: "indigo" | "amber" };
  actionLabel: string;
  actionTo: string;
}

export const ATTENTION_ITEMS: AttentionItem[] = [
  {
    id: "attn-1",
    icon: Mail,
    iconTone: "indigo",
    title: "Webhook reliability & EU hosting",
    meta: "Maya Chen · Northstar Logistics · 1 cited source",
    time: "Inbox Agent · 09:42",
    badge: { label: "Needs review", tone: "indigo" },
    actionLabel: "Review draft",
    actionTo: "/inbox-agent",
  },
  {
    id: "attn-2",
    icon: Layers,
    iconTone: "indigo",
    title: "Customer portal integration · scope v2",
    meta: "Discovery meeting · 5 requirements · 1 unresolved",
    time: "Meeting-to-Scope · 09:28",
    badge: { label: "Needs review", tone: "indigo" },
    actionLabel: "Review scope",
    actionTo: "/meeting-to-scope",
  },
  {
    id: "attn-3",
    icon: Flag,
    iconTone: "amber",
    title: "Confirm EU data residency",
    meta: "No source supports a regional hosting commitment",
    time: "Escalations · 09:15",
    badge: { label: "Missing evidence", tone: "amber" },
    actionLabel: "View escalation",
    actionTo: "/escalations",
  },
];

export interface SyncRow {
  name: string;
  synced: boolean;
  at: string;
}

export const SYNC_ROWS: SyncRow[] = [
  { name: "API guide v2.4", synced: true, at: "17 Oct, 16:40" },
  { name: "Security overview", synced: true, at: "17 Oct, 16:35" },
  { name: "Solution notes", synced: true, at: "17 Oct, 15:20" },
];

export const CLIENT_CONTEXT = {
  name: "Northstar Logistics",
  summary: "RelayOps customer portal integration Discovery → technical validation",
  owner: "Alex Morgan",
  project: "Project NS-104",
};
