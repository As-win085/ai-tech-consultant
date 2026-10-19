export interface TranscriptExcerpt {
  speaker: string;
  time: string;
  text: string;
}

export const TRANSCRIPT: TranscriptExcerpt[] = [
  {
    speaker: "Maya Chen",
    time: "08:14",
    text: "We need shipment updates in the portal without polling. Can you sign each event?",
  },
  {
    speaker: "Alex Morgan",
    time: "09:03",
    text: "We'll verify the delivery and retry behavior against the API guide.",
  },
  {
    speaker: "Jon Bell",
    time: "14:22",
    text: "Our support team needs an export of the audit trail for each customer.",
  },
  {
    speaker: "Maya Chen",
    time: "18:06",
    text: "Our policy requires customer data to stay in the EU. Please confirm before scope sign-off.",
  },
];

export interface ScopeDeltaLine {
  kind: "added" | "modified" | "unchanged";
  text: string;
}

export const SCOPE_DELTA: ScopeDeltaLine[] = [
  { kind: "added", text: "+ REQ-05: event deduplication" },
  { kind: "modified", text: "~ REQ-04: moved to clarification" },
  { kind: "unchanged", text: "Unchanged: 3 requirements" },
];

export type RequirementStatus = "reviewed" | "ai-suggestion" | "needs-clarification";
export type EvidenceState = "supported" | "conditional" | "unverified";

export interface Requirement {
  id: string;
  title: string;
  status: RequirementStatus;
  evidence: EvidenceState;
  evidenceCitation?: string;
  effort: string;
  effortExcluded?: boolean;
  assumption: string;
  /** Renders the card with an amber warning border when true. */
  flagged?: boolean;
}

export const REQUIREMENTS: Requirement[] = [
  {
    id: "REQ-01",
    title: "Validate signed webhook events",
    status: "reviewed",
    evidence: "supported",
    evidenceCitation: "[1] API guide §4.2",
    effort: "16-24 h",
    assumption: "Assumption: One endpoint; HMAC-SHA256 validation.",
  },
  {
    id: "REQ-02",
    title: "Ingest shipment status into the portal",
    status: "ai-suggestion",
    evidence: "conditional",
    evidenceCitation: "[1] API guide §4.2",
    effort: "16-24 h",
    assumption: "Assumption: Existing portal API; event mapping to be confirmed.",
  },
  {
    id: "REQ-03",
    title: "Export tenant audit records",
    status: "ai-suggestion",
    evidence: "conditional",
    evidenceCitation: "[2] Security overview §3.1",
    effort: "12-20 h",
    assumption: "Assumption: 90-day retention confirmed; export API access unverified.",
  },
  {
    id: "REQ-04",
    title: "Keep all customer data in the EU",
    status: "needs-clarification",
    evidence: "unverified",
    effort: "Excluded",
    effortExcluded: true,
    assumption: "Assumption: ESC-12 · Priya to confirm hosting and processing.",
    flagged: true,
  },
  {
    id: "REQ-05",
    title: "Deduplicate retried webhook events",
    status: "ai-suggestion",
    evidence: "supported",
    evidenceCitation: "[1] API guide §4.2",
    effort: "8-12 h",
    assumption: "Assumption: Event ID available; existing database can be reused.",
  },
];

export const EFFORT = {
  total: "68–104 hours",
  breakdown: "Build 52-80 h + validation 16-24 h",
  note: "Excludes EU hosting and migration",
};

export const DELIVERABLES: { title: string; detail: string }[] = [
  {
    title: "Signed webhook receiver",
    detail: "Signature validation and event deduplication.",
  },
  {
    title: "Portal event mapping",
    detail: "Shipment status updates through existing API.",
  },
  {
    title: "Audit export",
    detail: "Tenant-scoped CSV; documented 90-day window.",
  },
  {
    title: "Validation & handoff",
    detail: "Integration tests, retry tests, and runbook.",
  },
];
