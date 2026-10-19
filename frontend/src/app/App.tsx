import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ApiError } from "@/api/http";
import { WorkspaceShell } from "@/components/layout/WorkspaceShell";
import { DashboardView } from "@/features/dashboard/DashboardView";
import { KnowledgeBrainView } from "@/features/knowledge/KnowledgeBrainView";
import { InboxAgentView } from "@/features/inbox/InboxAgentView";
import { MeetingToScopeView } from "@/features/meeting/MeetingToScopeView";
import { KnowledgeManagementView } from "@/features/kmgmt/KnowledgeManagementView";
import { EscalationsView } from "@/features/escalations/EscalationsView";
import { PlaceholderView } from "@/features/governance/PlaceholderView";
import { OverviewPage } from "@/pages/Overview";
import { KnowledgePage } from "@/pages/Knowledge";
import { InboxPage } from "@/pages/Inbox";
import { MeetingPage } from "@/pages/MeetingToScope";
import { SettingsPage } from "@/pages/Settings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (failureCount, error) => {
        // Never retry aborted or client-side validation failures.
        if (error instanceof ApiError && (error.isAbort || error.kind === "aborted")) return false;
        if (error instanceof ApiError && error.kind === "http" && (error.status ?? 0) < 500) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<WorkspaceShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardView />} />
            <Route path="/knowledge-brain" element={<KnowledgeBrainView />} />
            <Route path="/inbox-agent" element={<InboxAgentView />} />
            <Route path="/meeting-to-scope" element={<MeetingToScopeView />} />
            <Route path="/knowledge-management" element={<KnowledgeManagementView />} />
            <Route path="/escalations" element={<EscalationsView />} />
            <Route
              path="/evaluations"
              element={
                <PlaceholderView
                  path="/evaluations"
                  title="Evaluations"
                  description="Score draft quality, citation accuracy, and grounding over time."
                />
              }
            />
            <Route
              path="/feedback-history"
              element={
                <PlaceholderView
                  path="/feedback-history"
                  title="Feedback History"
                  description="Every approval, rejection, and edit — with the draft it changed."
                />
              }
            />
            <Route
              path="/audit-logs"
              element={
                <PlaceholderView
                  path="/audit-logs"
                  title="Audit Logs"
                  description="Who sent what, which citations they saw, and when sources synced."
                />
              }
            />
            <Route path="/settings" element={<SettingsPage />} />

            {/* Legacy API-backed pages (live backend integration). */}
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/inbox" element={<InboxPage />} />
            <Route path="/meeting" element={<MeetingPage />} />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
