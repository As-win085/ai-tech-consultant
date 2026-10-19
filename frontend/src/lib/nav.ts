import {
  Brain,
  Database,
  FileText,
  Flag,
  FlaskConical,
  Inbox,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Optional count badge shown on the right of the nav row. */
  count?: number;
  /** Badge tone for the count pill. */
  countTone?: "indigo" | "amber";
  end?: boolean;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const WORKSPACE_NAV: NavSection["items"] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/knowledge-brain", label: "Knowledge Brain", icon: Brain },
  { to: "/inbox-agent", label: "Inbox Agent", icon: Inbox, count: 3, countTone: "indigo" },
  { to: "/meeting-to-scope", label: "Meeting-to-Scope", icon: FileText, count: 2, countTone: "indigo" },
  { to: "/knowledge-management", label: "Knowledge Management", icon: Database },
  { to: "/escalations", label: "Escalations", icon: Flag, count: 2, countTone: "amber" },
];

export const GOVERNANCE_NAV: NavSection["items"] = [
  { to: "/evaluations", label: "Evaluations", icon: FlaskConical },
  { to: "/feedback-history", label: "Feedback History", icon: MessageSquare },
  { to: "/audit-logs", label: "Audit Logs", icon: ShieldCheck },
  { to: "/settings", label: "Settings", icon: Settings },
];

export const NAV_SECTIONS: NavSection[] = [
  { title: "Workspace", items: WORKSPACE_NAV },
  { title: "Governance", items: GOVERNANCE_NAV },
];

/** Breadcrumb titles for the top bar, keyed by route path. */
export const ROUTE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/knowledge-brain": "Knowledge Brain",
  "/inbox-agent": "Inbox Agent",
  "/meeting-to-scope": "Meeting-to-Scope",
  "/knowledge-management": "Knowledge Management",
  "/escalations": "Escalations",
  "/evaluations": "Evaluations",
  "/feedback-history": "Feedback History",
  "/audit-logs": "Audit Logs",
  "/settings": "Settings",
  // Legacy API-backed pages (kept for live backend integration).
  "/overview": "Operations Overview",
  "/knowledge": "Knowledge Brain (Live)",
  "/inbox": "Inbox Agent (Live)",
  "/meeting": "Meeting-to-Scope (Live)",
};
