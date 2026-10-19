import type { LucideIcon } from "lucide-react";
import { FileText, Globe, Shield } from "lucide-react";

export const KM_KPIS = [
  { value: "8", label: "connected sources", tone: "default" },
  { value: "146", label: "indexed pages / records", tone: "default" },
  { value: "7", label: "fully synchronized", tone: "default" },
  { value: "1", label: "source needs attention", tone: "amber" },
] as const;

export type SourceStatus = "synced" | "partial";

export interface FailedPage {
  url: string;
  code: string;
  reason: string;
  detail: string;
}

export interface Source {
  id: string;
  name: string;
  icon: LucideIcon;
  type: string;
  indexed: string;
  status: SourceStatus;
  lastSync: string;
  lastAttempt?: string;
  owner: string;
  failedPages?: FailedPage[];
}

export const SOURCES: Source[] = [
  {
    id: "src-help",
    name: "RelayOps help center",
    icon: Globe,
    type: "Website",
    indexed: "46 / 48",
    status: "partial",
    lastSync: "17 Oct, 16:32",
    lastAttempt: "18 Oct, 08:10",
    owner: "Alex Morgan",
    failedPages: [
      {
        url: "/help/regional-hosting",
        code: "HTTP 403",
        reason: "Access denied",
        detail: "The page requires authorization. No content was indexed.",
      },
      {
        url: "/help/legacy-export",
        code: "HTTP 404",
        reason: "Not found",
        detail: "The source URL no longer resolves. No current evidence is available.",
      },
    ],
  },
  {
    id: "src-api",
    name: "RelayOps API guide",
    icon: FileText,
    type: "PDF",
    indexed: "38",
    status: "synced",
    lastSync: "17 Oct, 16:40",
    owner: "Alex Morgan",
  },
  {
    id: "src-security",
    name: "Security overview",
    icon: Shield,
    type: "PDF",
    indexed: "14",
    status: "synced",
    lastSync: "17 Oct, 16:35",
    owner: "Priya Shah",
  },
  {
    id: "src-notes",
    name: "Solution architecture notes",
    icon: FileText,
    type: "Document",
    indexed: "8",
    status: "synced",
    lastSync: "17 Oct, 15:20",
    owner: "Alex Morgan",
  },
];

export const SOURCE_IMPACT_WARNING =
  "Do not treat unavailable pages as evidence. Previously indexed, unaffected pages remain searchable.";
