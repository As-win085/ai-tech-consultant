/**
 * Environment-driven configuration for service endpoints.
 *
 * All service base URLs are supplied through `VITE_*` variables. No secrets may
 * ever be placed in these variables — they are bundled into the browser and are
 * not a safe place for credentials. The backends hold their own provider keys.
 */

const rawDemo = (import.meta.env.VITE_DEMO_MODE ?? "").toLowerCase();
const demoEnabled = rawDemo === "1" || rawDemo === "true" || rawDemo === "yes";

export interface ServiceConfig {
  knowledgeUrl: string;
  inboxUrl: string;
  meetingUrl: string;
  demoMode: boolean;
}

export const config: ServiceConfig = {
  knowledgeUrl: (import.meta.env.VITE_KNOWLEDGE_API_URL ?? "http://localhost:8000").replace(/\/$/, ""),
  inboxUrl: (import.meta.env.VITE_INBOX_API_URL ?? "http://localhost:8080").replace(/\/$/, ""),
  meetingUrl: (import.meta.env.VITE_MEETING_API_URL ?? "http://localhost:8090").replace(/\/$/, ""),
  demoMode: demoEnabled,
};

/** Guard used by pages to avoid live calls while demo fixtures are active. */
export const isDemo = config.demoMode;
