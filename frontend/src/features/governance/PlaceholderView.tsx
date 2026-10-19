import type { LucideIcon } from "lucide-react";
import { FlaskConical, MessageSquare, ShieldCheck } from "lucide-react";

const GOVERNANCE_CARDS: Record<string, { icon: LucideIcon; points: string[] }> = {
  "/evaluations": {
    icon: FlaskConical,
    points: [
      "Regression sets for draft quality and citation accuracy",
      "Score trends per source and per consultant",
      "Gate releases on evaluation passes",
    ],
  },
  "/feedback-history": {
    icon: MessageSquare,
    points: [
      "Approvals, rejections, and edits with the original draft",
      "Resolved escalations with decision rationale",
      "Feedback that feeds the next evaluation run",
    ],
  },
  "/audit-logs": {
    icon: ShieldCheck,
    points: [
      "Who approved which answer, and when",
      "Citations shown at the moment of send",
      "Source sync events and failures",
    ],
  },
};

export function PlaceholderView({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: string;
}) {
  const card = GOVERNANCE_CARDS[path];
  const Icon = card?.icon ?? FlaskConical;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
        <p className="text-xs text-slate-500">{description}</p>
      </div>

      <div className="mx-auto max-w-2xl rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
          <Icon className="h-6 w-6" aria-hidden="true" />
        </div>
        <h3 className="mt-4 text-sm font-bold text-slate-900">{title} is part of the governance suite</h3>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">
          The sample workspace ships the consultant views first. Governance data will land here once
          evaluations, feedback, and audit events start flowing from the live backend.
        </p>

        {card && (
          <ul className="mx-auto mt-5 max-w-xs space-y-2 text-left">
            {card.points.map((p) => (
              <li key={p} className="flex items-start gap-2 text-xs text-slate-600">
                <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" aria-hidden="true" />
                {p}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
