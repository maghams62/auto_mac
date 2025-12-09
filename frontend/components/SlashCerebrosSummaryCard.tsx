"use client";

import React, { useMemo } from "react";
import {
  SlashCerebrosSummaryPayload,
  SlashQueryPlan,
  DocPriority,
  IncidentCandidate,
  SourceDivergenceSummary,
  InformationGap,
} from "@/lib/useWebSocket";
import { useToast } from "@/lib/useToast";
import { openExternalUrl, copyToClipboard } from "@/lib/externalLinks";
import { IncidentCTA } from "./IncidentCTA";

interface SlashCerebrosSummaryCardProps {
  summary: SlashCerebrosSummaryPayload;
  queryPlan?: SlashQueryPlan;
  hideAnswerText?: boolean;
}

const Tag = ({ children }: { children: React.ReactNode }) => (
  <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-medium text-white/80">
    {children}
  </span>
);

const SlashCerebrosSummaryCard: React.FC<SlashCerebrosSummaryCardProps> = ({
  summary,
  queryPlan,
  hideAnswerText = false,
}) => {
  const { addToast } = useToast();
  const context = summary.context || {};
  const plan = context.query_plan || queryPlan;
  const modalities = context.modalities_used || summary.analysis?.modalities_used || [];
  const totalResults = context.total_results || summary.analysis?.result_count;
  const sources = summary.sources || [];
  const cerebrosAnswer = summary.cerebros_answer;
  const answerText = cerebrosAnswer?.answer || summary.message;
  const optionLabel = cerebrosAnswer?.option;
  const docPriorities = (cerebrosAnswer?.doc_priorities as DocPriority[]) || [];
  const components = cerebrosAnswer?.components || summary.analysis?.components || [];
  const incidentCandidate = summary.incident_candidate as IncidentCandidate | undefined;
  const entityCount = incidentCandidate?.incident_entities?.length ?? 0;
  const rootCause =
    cerebrosAnswer?.root_cause_explanation || incidentCandidate?.root_cause_explanation || answerText;
  const impactSummary = cerebrosAnswer?.impact_summary || incidentCandidate?.impact_summary;
  const resolutionPlan = normalizeResolutionPlan(
    (cerebrosAnswer?.resolution_plan as string[] | string | undefined) ||
      incidentCandidate?.resolution_plan,
  );
  const activitySignals = cerebrosAnswer?.activity_signals || incidentCandidate?.activity_signals;
  const dissatisfactionSignals =
    cerebrosAnswer?.dissatisfaction_signals || incidentCandidate?.dissatisfaction_signals;
  const dependencyImpact = cerebrosAnswer?.dependency_impact || incidentCandidate?.dependency_impact;
  const sourceDivergence =
    (cerebrosAnswer?.source_divergence as SourceDivergenceSummary | undefined) ||
    (incidentCandidate?.source_divergence as SourceDivergenceSummary | undefined);
  const informationGaps =
    (cerebrosAnswer?.information_gaps as InformationGap[] | undefined) ||
    (incidentCandidate?.information_gaps as InformationGap[] | undefined);
  const severityScore =
    typeof summary.data?.severity_score === "number"
      ? summary.data.severity_score
      : typeof summary.data?.severity?.score_0_10 === "number"
        ? summary.data.severity.score_0_10
        : 5;
  const severityLabel =
    summary.data?.severity_label ||
    summary.data?.severity?.label ||
    (docPriorities[0] as DocPriority | undefined)?.severity_label;
  const severityMeta = getSeverityMetadata(severityScore);

  const planBadges = useMemo(() => {
    const badges: Array<{ label: string; value: string }> = [];
    if (modalities?.length) {
      badges.push({ label: "Modalities", value: modalities.join(", ") });
    }
    if (typeof totalResults === "number") {
      badges.push({ label: "Matches", value: totalResults.toString() });
    }
    if (plan?.targets?.length) {
      const labels = plan.targets
        .map((target) => target.label || target.identifier || target.raw)
        .filter(Boolean);
      if (labels.length) {
        badges.push({ label: "Targets", value: labels.join(", ") });
      }
    }
    if (plan?.time_scope && typeof plan.time_scope === "object") {
      const scopeLabel = (plan.time_scope as Record<string, unknown>).label;
      if (scopeLabel && typeof scopeLabel === "string") {
        badges.push({ label: "Window", value: scopeLabel });
      }
    }
    if (plan?.intent) {
      badges.push({ label: "Intent", value: plan.intent });
    }
    return badges;
  }, [modalities, totalResults, plan]);

  const handleOpenLink = async (url?: string) => {
    if (!url) {
      addToast("Link unavailable for this source.", "warning");
      return;
    }
    const opened = openExternalUrl(url);
    if (!opened) {
      const copied = await copyToClipboard(url);
      addToast(copied ? "Couldn't open link, copied instead." : "Unable to open link.", copied ? "warning" : "error");
    }
  };

  const handleCopyLink = async (url?: string) => {
    if (!url) {
      addToast("Link unavailable for this source.", "warning");
      return;
    }
    const copied = await copyToClipboard(url);
    addToast(copied ? "Link copied to clipboard." : "Unable to copy link.", copied ? "success" : "error");
  };

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/20">
      <div className="flex flex-wrap items-center gap-2 text-xs text-white/70">
        <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">/cerebros</span>
        {optionLabel && <Tag>{optionLabel.replace(/_/g, " ")}</Tag>}
        {context.modalities_used?.length && <Tag>{context.modalities_used.join(", ")}</Tag>}
        {severityMeta && (
          <span
            className={
              "rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase " + severityMeta.className
            }
          >
            {(severityLabel || severityMeta.label) ?? "severity"} ({severityScore.toFixed(1)}/10)
          </span>
        )}
      </div>

      {!hideAnswerText && answerText ? (
        <p className="mt-3 text-base font-semibold leading-relaxed text-white">{answerText}</p>
      ) : null}

      {planBadges.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {planBadges.map((badge) => (
            <span
              key={`${badge.label}-${badge.value}`}
              className="rounded-full border border-white/15 bg-black/20 px-2 py-0.5 text-[11px] uppercase tracking-wide text-white/60"
            >
              {badge.label}: <span className="text-white/90">{badge.value}</span>
            </span>
          ))}
        </div>
      )}

      {components?.length > 0 && (
        <div className="mt-3 text-[11px] uppercase tracking-wide text-white/50">
          Components in scope: <span className="text-white/80">{components.join(", ")}</span>
        </div>
      )}
      {entityCount > 0 && (
        <div className="mt-2 text-[11px] uppercase tracking-wide text-white/50">
          Impacted entities: <span className="text-white/80">{entityCount}</span>
        </div>
      )}

      {docPriorities.length > 0 && (
        <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-white/60">Doc priorities</div>
          <ul className="mt-2 space-y-2">
            {docPriorities.slice(0, 4).map((priority) => (
              <li key={priority.doc_id || priority.doc_title} className="rounded-xl border border-white/10 bg-black/30 p-3">
                <div className="text-sm font-semibold text-white">{priority.doc_title || priority.doc_id}</div>
                <div className="text-[11px] uppercase tracking-wide text-white/40">
                  Severity: {priority.severity || "unknown"} · Score: {priority.score.toFixed(2)}
                </div>
                {priority.reason && <p className="mt-1 text-sm text-white/70">{priority.reason}</p>}
                {priority.doc_url && (
                  <button
                    type="button"
                    onClick={() => handleOpenLink(priority.doc_url)}
                    className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-white/80 hover:text-white"
                  >
                    Open doc <span aria-hidden="true">↗</span>
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(rootCause || impactSummary) && (
        <div className="mt-4 rounded-2xl border border-white/15 bg-black/30 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-white/60">Structured reasoning</div>
          {rootCause ? <p className="mt-2 text-sm text-white/80">{rootCause}</p> : null}
          {impactSummary ? <p className="mt-2 text-xs text-white/70">{impactSummary}</p> : null}
          {resolutionPlan?.length ? (
            <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-white/70">
              {resolutionPlan.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          ) : null}
          {sourceDivergence ? (
            <div className="mt-3 rounded-xl border border-amber-300/30 bg-amber-500/10 p-3">
              <div className="text-[11px] uppercase tracking-wide text-amber-100">Evidence divergence</div>
              {sourceDivergence.summary ? (
                <p className="mt-1 text-xs text-amber-50">{sourceDivergence.summary}</p>
              ) : null}
              {sourceDivergence.items?.length ? (
                <ul className="mt-2 space-y-1 text-xs text-amber-50">
                  {sourceDivergence.items.slice(0, 3).map((item, idx) => (
                    <li key={`${item.source1 || "sourceA"}-${item.source2 || "sourceB"}-${idx}`}>
                      <span className="font-semibold">{item.source1 || "Source A"}</span> vs{" "}
                      <span className="font-semibold">{item.source2 || "Source B"}</span>:{" "}
                      {item.description || "Conflict detected"}
                    </li>
                  ))}
                  {sourceDivergence.count && sourceDivergence.items.length < sourceDivergence.count ? (
                    <li className="text-[11px] text-amber-200/80">
                      +{sourceDivergence.count - sourceDivergence.items.length} more divergence
                      {sourceDivergence.count - sourceDivergence.items.length === 1 ? "" : "s"}
                    </li>
                  ) : null}
                </ul>
              ) : null}
            </div>
          ) : null}
          {informationGaps?.length ? (
            <div className="mt-3 rounded-xl border border-sky-300/30 bg-sky-500/10 p-3">
              <div className="text-[11px] uppercase tracking-wide text-sky-100">Information gaps</div>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-sky-50">
                {informationGaps.slice(0, 4).map((gap, idx) => (
                  <li key={`${gap.description}-${idx}`}>
                    {gap.description}
                    {gap.type ? <span className="text-sky-200/80"> ({gap.type})</span> : null}
                  </li>
                ))}
                {informationGaps.length > 4 ? (
                  <li className="text-[11px] text-sky-200/80">
                    +{informationGaps.length - 4} additional gap
                    {informationGaps.length - 4 === 1 ? "" : "s"}
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}
        </div>
      )}

      {Boolean(activitySignals || dissatisfactionSignals) ? (
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          {renderSignalChips(activitySignals, "activity")}
          {renderSignalChips(dissatisfactionSignals, "dissatisfaction")}
        </div>
      ) : null}

      {dependencyImpact ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs text-white/70">
          <div className="text-[11px] uppercase tracking-wide text-white/50">Cross-system impact</div>
          {Array.isArray((dependencyImpact as any)?.impacts) ? (
            <ul className="mt-2 space-y-1">
              {(dependencyImpact as any).impacts.slice(0, 3).map((impact: any, idx: number) => (
                <li key={impact.componentId ?? idx}>
                  <span className="text-white/80">{impact.componentId || "Unknown component"}</span>
                  {impact.dependentComponents?.length ? (
                    <span className="text-white/50">
                      {" "}
                      → {impact.dependentComponents.slice(0, 3).join(", ")}
                      {impact.dependentComponents.length > 3 ? "…" : ""}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2">Impacts span multiple components.</p>
          )}
        </div>
      ) : null}

      {incidentCandidate ? (
        <IncidentCTA
          candidate={incidentCandidate}
          incidentId={summary.incident_id}
          investigationId={summary.investigation_id}
          className="mt-4"
        />
      ) : null}

      <div className="mt-4 rounded-2xl border border-white/15 bg-white/5 p-4">
        <div className="flex items-center gap-2">
          <span className="text-xl text-white">⌘</span>
          <div>
            <p className="text-sm font-semibold text-white">Sources</p>
            <p className="text-[11px] uppercase tracking-wide text-white/50">Deep links across modalities</p>
          </div>
        </div>
        {sources.length ? (
          <div className="mt-4 space-y-3">
            {sources.map((source, idx) => (
              <div key={source.id || `${source.type}-${idx}`} className="rounded-2xl border border-white/10 bg-black/25 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-white">{source.label}</span>
                    {source.type && (
                      <span className="text-[10px] uppercase tracking-wide text-white/40">{source.type}</span>
                    )}
                  </div>
                  {typeof source.score === "number" && (
                    <span className="text-[10px] uppercase tracking-wide text-white/40">Score {source.score.toFixed(2)}</span>
                  )}
                </div>
                {source.snippet && <p className="mt-2 text-sm text-white/80">{source.snippet}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => handleOpenLink(source.url)}
                    className="inline-flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-xs font-semibold text-white/80 transition hover:border-white/40 hover:text-white"
                  >
                    Open
                    <span aria-hidden="true">↗</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCopyLink(source.url)}
                    className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 text-[11px] font-medium text-white/70 transition hover:border-white/30 hover:text-white"
                  >
                    Copy link
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-white/60">No linked sources were returned for this query.</p>
        )}
      </div>
    </div>
  );
};

export default SlashCerebrosSummaryCard;

const SIGNAL_DESCRIPTORS: Record<string, { label: string; prefix: string }> = {
  git_events: { label: "Git", prefix: "🔥" },
  git_items: { label: "Git", prefix: "🔥" },
  slack_threads: { label: "Slack", prefix: "💬" },
  slack_conversations: { label: "Slack", prefix: "💬" },
  slack_complaints: { label: "Complaints", prefix: "😡" },
  support_complaints: { label: "Support", prefix: "😡" },
  doc_issues: { label: "Doc issues", prefix: "📄" },
  issues: { label: "Tickets", prefix: "📨" },
};

function renderSignalChips(
  signals?: Record<string, number>,
  variant: "activity" | "dissatisfaction" = "activity",
) {
  if (!signals) return null;
  return Object.entries(signals)
    .filter(([, value]) => typeof value === "number" && value > 0)
    .map(([key, value]) => {
      const descriptor = SIGNAL_DESCRIPTORS[key] || {
        label: key.replace(/_/g, " "),
        prefix: variant === "activity" ? "🔥" : "😡",
      };
      return (
        <span
          key={`${variant}-${key}`}
          className={
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold " +
            (variant === "activity" ? "border-emerald-400/40 text-emerald-100" : "border-rose-400/40 text-rose-100")
          }
        >
          {descriptor.prefix} {descriptor.label} <span className="font-bold">{value}</span>
        </span>
      );
    });
}

function normalizeResolutionPlan(value?: string[] | string): string[] | undefined {
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

function getSeverityMetadata(score?: number):
  | {
      label: string;
      className: string;
    }
  | undefined {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return undefined;
  }

  if (score < 3) {
    return { label: "low severity", className: "border-emerald-400/40 bg-emerald-500/10 text-emerald-100" };
  }
  if (score < 6) {
    return { label: "medium severity", className: "border-amber-400/40 bg-amber-500/10 text-amber-100" };
  }
  return { label: "high severity", className: "border-rose-400/40 bg-rose-500/10 text-rose-100" };
}

