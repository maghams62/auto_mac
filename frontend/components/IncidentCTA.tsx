// IncidentCTA.tsx
"use client";

import { useState } from "react";
import { IncidentCandidate } from "@/lib/useWebSocket";
import { getApiBaseUrl } from "@/lib/apiConfig";
import { useToast } from "@/lib/useToast";
import { buildDashboardIncidentUrl, hasDashboardBase } from "@/lib/dashboardLinks";
import { cn } from "@/lib/utils";

const severityStyles: Record<IncidentCandidate["severity"], string> = {
  critical: "bg-red-500/15 text-red-200 border-red-500/30",
  high: "bg-orange-500/15 text-orange-200 border-orange-500/30",
  medium: "bg-amber-500/15 text-amber-200 border-amber-500/30",
  low: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
};

type IncidentCTAProps = {
  candidate: IncidentCandidate;
  investigationId?: string;
  incidentId?: string;
  className?: string;
};

export function IncidentCTA({ candidate, investigationId, incidentId, className }: IncidentCTAProps) {
  const [creating, setCreating] = useState(false);
  const [createdIncidentId, setCreatedIncidentId] = useState<string | undefined>(incidentId);
  const { addToast } = useToast();
  const counts = candidate.counts || {};
  const resolutionPlan = normalizePlan(candidate.resolution_plan);
  const impactedEntities = candidate.incident_entities?.length ?? 0;

  const scopeSummary = [
    counts.components ? `${counts.components} components` : null,
    counts.docs ? `${counts.docs} docs` : null,
    counts.issues ? `${counts.issues} tickets` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const incidentUrl = createdIncidentId ? buildDashboardIncidentUrl(createdIncidentId) : undefined;

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const apiBase = getApiBaseUrl();
      const response = await fetch(`${apiBase}/api/incidents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          incident_candidate: candidate,
          investigation_id: investigationId,
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const payload = await response.json();
      setCreatedIncidentId(payload.id as string);
      addToast("Incident created in dashboard.", "success");
    } catch (error) {
      console.error("Failed to create incident", error);
      addToast("Failed to create incident.", "error");
    } finally {
      setCreating(false);
    }
  };

  const handleMissingDashboard = () => {
    addToast(
      "Dashboard base URL is not configured; set NEXT_PUBLIC_DASHBOARD_BASE_URL to enable deep links.",
      "warning",
    );
  };

  return (
    <div className={cn("rounded-2xl border border-white/15 bg-white/5 p-4 shadow-inner shadow-black/10", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-white/70">Incident candidate</p>
          <h3 className="text-base font-semibold text-white">{candidate.summary}</h3>
          <p className="text-xs text-white/70">{scopeSummary || "Multi-modal evidence collected"}</p>
        </div>
        <div
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide",
            severityStyles[candidate.severity ?? "low"],
          )}
        >
          {candidate.severity} · {Math.round(candidate.blast_radius_score ?? 0)}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-white/80">
        {counts.evidence ? (
          <span className="rounded-full border border-white/15 px-2 py-0.5">
            {counts.evidence} evidence items
          </span>
        ) : null}
        {candidate.recency_info?.most_recent ? (
          <span className="rounded-full border border-white/15 px-2 py-0.5">
            Last signal {candidate.recency_info.hours_since?.toFixed?.(1) ?? "?"}h ago
          </span>
        ) : null}
        {candidate.source_command ? (
          <span className="rounded-full border border-white/15 px-2 py-0.5">
            Source • {candidate.source_command.replace(/_/g, " ")}
          </span>
        ) : null}
        {impactedEntities > 0 ? (
          <span className="rounded-full border border-white/15 px-2 py-0.5">
            {impactedEntities} impacted {impactedEntities === 1 ? "entity" : "entities"}
          </span>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {candidate.root_cause_explanation ? (
          <p className="w-full text-xs text-white/70">
            Root cause: <span className="text-white/90">{candidate.root_cause_explanation}</span>
          </p>
        ) : null}
        {resolutionPlan?.length ? (
          <ul className="w-full list-disc space-y-1 pl-5 text-xs text-white/80">
            {resolutionPlan.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        ) : null}

        {createdIncidentId ? (
          incidentUrl && hasDashboardBase() ? (
            <a
              href={incidentUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-full bg-white/15 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white transition hover:bg-white/25"
            >
              View incident ↗
            </a>
          ) : (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full border border-white/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white/80 transition hover:border-white/40 hover:text-white"
              onClick={handleMissingDashboard}
            >
              Incident {createdIncidentId}
            </button>
          )
        ) : (
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-white transition",
              creating ? "opacity-60" : "hover:border-white/40 hover:text-white",
            )}
          >
            {creating ? "Creating…" : "Create incident"}
          </button>
        )}
        {candidate.raw_trace_id ? (
          <a
            href={`/brain/trace/${candidate.raw_trace_id}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 text-[11px] font-semibold text-white/70 transition hover:border-white/30 hover:text-white"
          >
            Brain trace
          </a>
        ) : null}
      </div>
    </div>
  );
}

function normalizePlan(value: IncidentCandidate["resolution_plan"]): string[] | undefined {
  if (!value) return undefined;
  if (Array.isArray(value)) {
    const normalized = value.map((entry) => entry?.trim()).filter(Boolean) as string[];
    return normalized.length ? normalized : undefined;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : undefined;
  }
  return undefined;
}

