export interface Conversation {
  id: string;
  title: string;
  meta: string;
}

export const CONVERSATIONS: Conversation[] = [
  { id: "c-1", title: "Webhook reliability", meta: "Northstar · 09:12" },
  { id: "c-2", title: "Audit export limits", meta: "Northstar · 08:50" },
  { id: "c-3", title: "Tenant isolation", meta: "Northstar · 08:32" },
];

export interface AnswerSection {
  heading: string;
  body: string;
  citation: string;
}

export const QUESTION = {
  author: "Alex Morgan",
  time: "09:12",
  project: "Northstar",
  text: "Can RelayOps support Northstar's signed webhooks, retry needs, and EU hosting requirement?",
};

export const ANSWER = {
  headline: "Signed delivery and retries are documented. EU data residency is not yet established.",
  citedSources: 2,
  evidenceGaps: 1,
  sections: [
    {
      heading: "Signed webhook delivery:",
      body: "RelayOps signs events with HMAC-SHA256. Northstar's endpoint should validate the signature before accepting the payload.",
      citation: "[1]",
    },
    {
      heading: "Retry behavior:",
      body: "Failed deliveries use exponential backoff for up to 24 hours. This supports transient outages, but the source does not promise exactly-once delivery.",
      citation: "[1]",
    },
    {
      heading: "Audit and isolation:",
      body: "The security overview describes tenant-isolated access and 90-day audit retention. It does not identify a dedicated EU hosting region.",
      citation: "[2]",
    },
  ] satisfies AnswerSection[],
};

export const MISSING_EVIDENCE = {
  title: "Missing evidence · EU data residency",
  body: "No indexed source confirms EU-only storage or processing. Do not promise regional hosting. Priya Shah is reviewing escalation ESC-12.",
  escalation: "ESC-12",
};

export const EVIDENCE_PANEL = {
  source: "RelayOps API guide",
  section: "Webhooks / Delivery & retries · Last synced 17 Oct",
  passageLabel: "MATCHED PASSAGE · §4.2",
  passage: "Each event is signed using HMAC-SHA256. Failed deliveries are retried... up to 24 hours.",
  related: {
    marker: "[2]",
    label: "Security overview · §3.1 Tenant isolation & audit retention",
  },
};
