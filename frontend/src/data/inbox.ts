export type QueueBadge = "needs-review" | "escalated";

export interface QueueItem {
  id: string;
  sender: string;
  time: string;
  subject: string;
  badge: QueueBadge;
  projectRef: string;
  draftVersion: string;
  /** Original inbound email body. */
  original: string;
  /** AI-generated draft paragraphs; `{{n}}` marks inline citations. */
  draft: string[];
  citations: { marker: string; label: string }[];
  /** Optional warning about removed unsupported claims. */
  removedClaim?: { title: string; body: string };
  evidence: {
    source: string;
    section: string;
    synced: string;
    passage: string;
    highlighted: string;
    rest: string;
  };
}

export const QUEUE: QueueItem[] = [
  {
    id: "q-1",
    sender: "Maya Chen",
    time: "09:42",
    subject: "Webhook reliability & EU hosting",
    badge: "needs-review",
    projectRef: "NS-104 · Draft v1",
    draftVersion: "Draft v1",
    original:
      "Hi Alex,\n\nBefore we finalize the portal integration, can you confirm how RelayOps signs webhooks and handles failed deliveries?\n\nOur team also needs EU-only hosting. Can you confirm this is included in the proposed approach?\n\nIf our endpoint is down overnight, will events still arrive the next day?\n\nThanks,\nMaya",
    draft: [
      "Hi Maya,",
      "RelayOps signs webhook events using HMAC-SHA256. We'll include signature validation and event-ID deduplication in the integration. {{1}}",
      "Failed deliveries are retried with exponential backoff for up to 24 hours. An overnight outage may be covered within that window, but delivery beyond 24 hours is not documented. {{1}}",
      "I can't yet confirm EU-only hosting. We've asked our security lead to verify the available regions before we commit to this in the scope.",
      "Could you share your required recovery window and any data residency policy?",
      "Best,\nAlex",
    ],
    citations: [{ marker: "[1]", label: "API guide §4.2" }],
    removedClaim: {
      title: "Unsupported claim removed",
      body: "“EU-only hosting is included” has no supporting evidence. Keep the qualification or resolve ESC-12 before promising it.",
    },
    evidence: {
      source: "RelayOps API guide",
      section: "Webhooks / Delivery & retries · Last synced 17 Oct",
      synced: "17 Oct",
      passage:
        "Each event is signed using HMAC-SHA256. Failed deliveries are retried with exponential backoff for up to 24 hours. Consumers must deduplicate using the event ID.",
      highlighted:
        "Each event is signed using HMAC-SHA256. Failed deliveries are retried with exponential backoff for up to 24 hours.",
      rest: " Consumers must deduplicate using the event ID.",
    },
  },
  {
    id: "q-2",
    sender: "Jon Bell",
    time: "08:56",
    subject: "Audit export access request",
    badge: "needs-review",
    projectRef: "NS-104 · Draft v1",
    draftVersion: "Draft v1",
    original:
      "Hi Alex,\n\nOur support leads need programmatic access to the tenant audit trail. What does the current export surface look like, and can we scope it for the portal work?\n\n— Jon",
    draft: [
      "Hi Jon,",
      "The security overview documents tenant-isolated audit access with a 90-day retention window. {{1}}",
      "We've listed a tenant-scoped CSV export as a proposed deliverable in scope v2, but export API access is still unverified — I'll confirm feasibility before we commit.",
      "Best,\nAlex",
    ],
    citations: [{ marker: "[1]", label: "Security overview §3.1" }],
    evidence: {
      source: "Security overview",
      section: "Tenant isolation & audit retention · Last synced 17 Oct",
      synced: "17 Oct",
      passage:
        "Audit records are retained for 90 days and are tenant-isolated. Dedicated export endpoints are not documented in this revision.",
      highlighted:
        "Audit records are retained for 90 days and are tenant-isolated.",
      rest: " Dedicated export endpoints are not documented in this revision.",
    },
  },
  {
    id: "q-3",
    sender: "Maya Chen",
    time: "08:20",
    subject: "Portal launch dependencies",
    badge: "needs-review",
    projectRef: "NS-104 · Draft v1",
    draftVersion: "Draft v1",
    original:
      "Hi Alex,\n\nWhat are the hard dependencies for the portal launch date? We need to lock the plan by Friday.\n\nMaya",
    draft: [
      "Hi Maya,",
      "Based on the discovery notes, the critical path is the signed webhook receiver and event mapping; validation and handoff follow. {{1}}",
      "Two items are still open: EU hosting confirmation (ESC-12) and export API verification. Those could affect the date if unresolved.",
      "Best,\nAlex",
    ],
    citations: [{ marker: "[1]", label: "Solution notes §2" }],
    evidence: {
      source: "Solution architecture notes",
      section: "Integration sequencing · Last synced 17 Oct",
      synced: "17 Oct",
      passage:
        "Critical path: signed receiver → event mapping → validation. Handoff documentation completes the sequence.",
      highlighted:
        "Critical path: signed receiver → event mapping → validation.",
      rest: " Handoff documentation completes the sequence.",
    },
  },
  {
    id: "q-4",
    sender: "Priya Shah",
    time: "Yesterday",
    subject: "Regional hosting confirmation",
    badge: "escalated",
    projectRef: "NS-104 · ESC-12",
    draftVersion: "Escalated",
    original:
      "Hi Alex,\n\nFollowing the discovery call — legal is asking whether we can commit to EU-only processing for Northstar. Do we have a written answer yet?\n\nPriya",
    draft: [
      "Hi Priya,",
      "No indexed source confirms EU-only storage or processing, so I can't produce a written commitment yet. ESC-12 is open and assigned to you for review.",
      "Once hosting regions are confirmed by the security lead, I can update the scope and respond to Northstar.",
      "Best,\nAlex",
    ],
    citations: [],
    removedClaim: {
      title: "No evidence available",
      body: "The failed /help/regional-hosting page (HTTP 403) may have contained the answer. It is not indexed, so it cannot be cited.",
    },
    evidence: {
      source: "RelayOps help center",
      section: "Regional hosting · FAILED SYNC",
      synced: "17 Oct, 16:32",
      passage:
        "Page /help/regional-hosting could not be retrieved (HTTP 403 · Access denied). No content was indexed.",
      highlighted: "HTTP 403 · Access denied.",
      rest: " The page requires authorization. No content was indexed.",
    },
  },
];
