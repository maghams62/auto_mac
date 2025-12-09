"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AskCerebrosCopyButton } from "@/components/common/ask-cerebros-button";
import SeverityDetailsDialog from "@/components/SeverityDetailsDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  IncidentRecord,
  InvestigationEvidence,
  SeverityDetailsPayload,
  SeveritySemanticPair,
  SeverityExplanation,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { buildBrainTraceLink, buildBrainUniverseLink, buildDocLink, buildRepoLink } from "@/lib/link-builders";
import { buildEvidenceLookup, type EvidenceLookup, getEvidenceAnchorId, resolveEvidenceHref } from "./evidence-utils";
import IncidentReportTable from "./IncidentReportTable";
import IncidentVisualizations from "./IncidentVisualizations";

const severityTone: Record<string, string> = {
  critical: "bg-red-500/15 text-red-100 border-red-500/30",
  high: "bg-orange-500/15 text-orange-100 border-orange-500/30",
  medium: "bg-amber-500/15 text-amber-100 border-amber-500/30",
  low: "bg-emerald-500/15 text-emerald-100 border-emerald-500/30",
};

const DEFAULT_GRAPH_CYPHER = "MATCH (n) RETURN n LIMIT 25";

interface IncidentDetailClientProps {
  incidentId: string;
}

type CandidateSnapshot = {
  incident_candidate_snapshot?: {
    doc_priorities?: Array<Record<string, unknown>>;
    evidence?: InvestigationEvidence[];
    severity_payload?: Record<string, unknown>;
    severity_breakdown?: Record<string, number>;
    severity_details?: SeverityDetailsPayload;
    severity_contributions?: Record<string, number>;
    severity_weights?: Record<string, number>;
    severity_semantic_pairs?: Record<string, SeveritySemanticPair>;
    severity_score?: number;
    severity_score_100?: number;
    severity_explanation?: SeverityExplanation;
  };
};

export default function IncidentDetailClient({ incidentId }: IncidentDetailClientProps) {
  const router = useRouter();
  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setStatus("loading");
        const response = await fetch(`/api/incidents/${incidentId}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Request failed (${response.status})`);
        }
        const payload = await response.json();
        if (!cancelled) {
          setIncident(payload?.data?.incident ?? null);
          setStatus("ready");
        }
      } catch (error) {
        console.error("Failed to load incident", error);
        if (!cancelled) {
          setStatus("error");
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  const metadataSnapshot = (incident?.metadata as CandidateSnapshot | undefined) ?? undefined;
  const candidateSnapshot = metadataSnapshot?.incident_candidate_snapshot;
  const docPriorities = useMemo(() => {
    if (incident?.docPriorities && incident.docPriorities.length > 0) {
      return incident.docPriorities;
    }
    return candidateSnapshot?.doc_priorities ?? [];
  }, [incident?.docPriorities, candidateSnapshot]);

  const evidenceItems = useMemo(() => {
    if (incident?.evidence && incident.evidence.length > 0) {
      return incident.evidence;
    }
    return candidateSnapshot?.evidence ?? [];
  }, [incident?.evidence, candidateSnapshot]);

  const evidenceLookup = useMemo<EvidenceLookup>(() => buildEvidenceLookup(evidenceItems), [evidenceItems]);
  const aggregatedSignals = useMemo<{
    activitySignals?: Record<string, number>;
    dissatisfactionSignals?: Record<string, number>;
  }>(() => {
    if (!incident) return {};
    return aggregateEntitySignals(incident);
  }, [incident]);
  const baseActivitySignals = incident?.activitySignals ?? aggregatedSignals.activitySignals;
  const baseDissatisfactionSignals = incident?.dissatisfactionSignals ?? aggregatedSignals.dissatisfactionSignals;
  const resolvedActivityScore = resolveActivityScore(incident?.activityScore, baseActivitySignals);
  const resolvedDissatisfactionScore = resolveDissatisfactionScore(
    incident?.dissatisfactionScore,
    baseActivitySignals,
    baseDissatisfactionSignals,
  );
  const incidentTitle = incident ? deriveIncidentTitle(incident) : "Incident";
  const incidentSummary = incident ? deriveIncidentSummary(incident) : null;
  const createdAt = incident ? new Date(incident.createdAt).toLocaleString() : "";
  const activityChip =
    typeof resolvedActivityScore === "number" ? `Activity score · ${resolvedActivityScore.toFixed(1)}` : null;
  const dissatisfactionChip =
    typeof resolvedDissatisfactionScore === "number"
      ? `Dissatisfaction · ${resolvedDissatisfactionScore.toFixed(1)}`
      : null;
  const brainTraceHref = buildBrainTraceLink(incident?.rawTraceId, incident?.brainTraceUrl);
  const brainUniverseHref = buildBrainUniverseLink(incident?.brainUniverseUrl);

  if (status === "loading") {
    return <p className="p-8 text-sm text-muted-foreground">Loading incident…</p>;
  }
  if (status === "error" || !incident) {
    return (
      <div className="space-y-4 p-8">
        <p className="text-sm text-amber-500">Unable to load this incident.</p>
        <Button variant="outline" onClick={() => router.back()}>
          Go back
        </Button>
      </div>
    );
  }

  const counts = incident.counts || {};

  return (
    <div className="space-y-8">
      <div className="space-y-4 border-b border-border/40 pb-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="max-w-5xl space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">Incident</p>
            <h1 className="text-2xl font-semibold text-foreground md:text-3xl">{incidentTitle}</h1>
            <p className="text-xs text-muted-foreground">Promoted from multi-modal reasoning · {createdAt}</p>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              {counts.components ? <span>{counts.components} components</span> : null}
              {counts.docs ? <span>{counts.docs} docs</span> : null}
              {counts.issues ? <span>{counts.issues} tickets</span> : null}
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              {activityChip ? (
                <span className="rounded-full border border-emerald-500/40 bg-emerald-500/5 px-3 py-1 text-[11px] font-semibold text-emerald-200">
                  {activityChip}
                </span>
              ) : null}
              {dissatisfactionChip ? (
                <span className="rounded-full border border-rose-500/40 bg-rose-500/5 px-3 py-1 text-[11px] font-semibold text-rose-200">
                  {dissatisfactionChip}
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className={severityTone[incident.severity] ?? severityTone["medium"]}>
              {incident.severity}
            </Badge>
            <Badge variant="outline" className="rounded-full border-border/50 text-[10px] uppercase">
              {incident.status}
            </Badge>
            {incident.projectId ? (
              <Badge variant="outline" className="rounded-full border-border/50 text-[10px] uppercase">
                Project {incident.projectId}
              </Badge>
            ) : null}
            {brainTraceHref ? (
              <Button asChild variant="outline" size="sm" className="rounded-full text-[11px] uppercase tracking-wide">
                <Link href={brainTraceHref} target="_blank" rel="noreferrer">
                  Generate full report ↗
                </Link>
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <SeverityBreakdownPanel incident={incident} candidateSnapshot={candidateSnapshot} />
      <StructuredReasoningPanel incident={incident} />
      <SignalsPanel
        incident={incident}
        activitySignals={baseActivitySignals}
        dissatisfactionSignals={baseDissatisfactionSignals}
        activityScore={resolvedActivityScore}
        dissatisfactionScore={resolvedDissatisfactionScore}
      />
      <IncidentVisualizations incident={incident} evidenceItems={evidenceItems} />
      <IncidentReportTable incident={incident} evidenceLookup={evidenceLookup} />
      <DependencyPanel incident={incident} />
      <GraphQueryPanel incident={incident} />
      <EvidencePanel
        docPriorities={docPriorities}
        evidenceItems={evidenceItems}
        brainTraceHref={brainTraceHref}
        brainUniverseHref={brainUniverseHref}
      />
    </div>
  );
}

function SeverityBreakdownPanel({
  incident,
  candidateSnapshot,
}: {
  incident: IncidentRecord;
  candidateSnapshot?: CandidateSnapshot["incident_candidate_snapshot"];
}) {
  const [showDetails, setShowDetails] = useState(false);
  const fallback = candidateSnapshot ?? {};
  const severityScore =
    typeof incident.severityScore === "number"
      ? incident.severityScore
      : typeof fallback.severity_score === "number"
        ? fallback.severity_score
        : undefined;
  const severityScore100 =
    typeof incident.severityScore100 === "number"
      ? incident.severityScore100
      : typeof fallback.severity_score_100 === "number"
        ? fallback.severity_score_100
        : undefined;
  const breakdown =
    incident.severityBreakdown ??
    (fallback.severity_breakdown as Record<string, number> | undefined);
  const details =
    incident.severityDetails ??
    (fallback.severity_details as SeverityDetailsPayload | undefined);
  const contributions =
    incident.severityContributions ??
    (fallback.severity_contributions as Record<string, number> | undefined);
  const weights =
    incident.severityWeights ??
    (fallback.severity_weights as Record<string, number> | undefined);
  const semanticPairs =
    incident.severitySemanticPairs ??
    (fallback.severity_semantic_pairs as Record<string, SeveritySemanticPair> | undefined);
  const severityExplanation =
    incident.severityExplanation ??
    (fallback.severity_explanation as SeverityExplanation | undefined);
  const crtScore =
    typeof severityScore === "number"
      ? severityScore
      : typeof severityScore100 === "number"
        ? severityScore100 / 10
        : undefined;

  if (!breakdown && crtScore === undefined) {
    return null;
  }

  const rows = buildSeverityRows({
    breakdown,
    weights,
    contributions,
    details,
    semanticPairs,
  });
  const semanticRowCount = Object.keys(semanticPairs ?? {}).length;
  const semanticList = Object.entries(semanticPairs ?? {}).map(([name, pair]) => ({
    name,
    cosine: pair?.cosine,
    drift: pair?.drift,
    matches: pair?.matches,
  }));

  const sourcesByWeightLabel = useMemo(() => {
    if (!weights) return undefined;
    const entries = Object.entries(weights)
      .filter(([, value]) => typeof value === "number" && value > 0)
      .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
    if (!entries.length) return undefined;
    const labelForKey: Record<string, string> = {
      slack: "Slack",
      git: "Git",
      doc: "Docs / doc issues",
      semantic: "Semantic",
      graph: "Graph",
    };
    return entries
      .map(([key, value]) => {
        const label = labelForKey[key] ?? key;
        return `${label} ${asPercent(value, 0)}`;
      })
      .join(" · ");
  }, [weights]);

  return (
    <section className="space-y-4 rounded-3xl border border-border/50 bg-background/70 p-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Severity breakdown</h2>
          <p className="text-xs text-muted-foreground">
            Weighted contribution of each modality to the CRT severity score.
          </p>
          {sourcesByWeightLabel ? (
            <p className="text-xs font-medium text-muted-foreground/90">
              Sources by weight: <span className="font-semibold text-foreground/90">{sourcesByWeightLabel}</span>
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border/60 px-3 py-1 text-sm font-semibold text-foreground">
          <span className="uppercase tracking-wide text-xs text-muted-foreground">CRT</span>
          <span>{incident.severity}</span>
          {crtScore !== undefined ? <span>· {crtScore.toFixed(1)} / 10</span> : null}
        </div>
      </div>

      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-4 font-semibold">Source</th>
                <th className="py-2 pr-4 font-semibold">Score</th>
                <th className="py-2 pr-4 font-semibold">Weight</th>
                <th className="py-2 pr-4 font-semibold">Contribution</th>
                <th className="py-2 font-semibold">Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-t border-border/30 text-foreground">
                  <td className="py-3 pr-4 font-medium">{row.label}</td>
                  <td className="py-3 pr-4">{row.score ?? "—"}</td>
                  <td className="py-3 pr-4">{row.weight ?? "—"}</td>
                  <td className="py-3 pr-4">{row.contribution ?? "—"}</td>
                  <td className="py-3 text-sm text-muted-foreground">{row.note ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No severity aggregates were attached to this incident.</p>
      )}

      {semanticRowCount > 0 ? (
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Semantic drift pairs</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">Pair</th>
                  <th className="py-2 pr-4 font-semibold">Cosine</th>
                  <th className="py-2 pr-4 font-semibold">Drift</th>
                  <th className="py-2 font-semibold">Matches</th>
                </tr>
              </thead>
              <tbody>
                {semanticList.map((pair) => (
                  <tr key={pair.name} className="border-t border-border/30 text-foreground">
                    <td className="py-2 pr-4 font-medium">{formatSemanticLabel(pair.name)}</td>
                    <td className="py-2 pr-4">{pair.cosine !== undefined ? pair.cosine.toFixed(3) : "—"}</td>
                    <td className="py-2 pr-4">{pair.drift !== undefined ? pair.drift.toFixed(3) : "—"}</td>
                    <td className="py-2">{pair.matches ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {severityExplanation ? (
        <>
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={() => setShowDetails(true)}>
              View full math breakdown
            </Button>
          </div>
          <SeverityDetailsDialog
            open={showDetails}
            onClose={() => setShowDetails(false)}
            severityLabel={incident.severity}
            severityScore={crtScore}
            explanation={severityExplanation}
            breakdown={breakdown}
            weights={weights ?? undefined}
            contributions={contributions ?? undefined}
          />
        </>
      ) : null}
    </section>
  );
}

function StructuredReasoningPanel({ incident }: { incident: IncidentRecord }) {
  const resolutionPlan = incident.resolutionPlan || [];
  const divergence = incident.sourceDivergence;
  const divergenceItems = divergence?.items ?? [];
  const informationGaps = incident.informationGaps || [];
  const summaryText = (incident.answer || incident.summary || "").trim();
  const structuredSummary = useMemo(() => parseStructuredSummary(summaryText), [summaryText]);
  return (
    <div
      className="space-y-4 rounded-3xl border border-border/50 bg-background/70 p-5"
      data-testid="incident-detail-root-cause"
    >
      <h2 className="text-lg font-semibold text-foreground">Structured reasoning</h2>
      {structuredSummary ? (
        <>
          <SectionBlock title="Doc / drift" body={structuredSummary.drift} />
          <SectionBlock title="Canonical current truth" body={structuredSummary.canonicalTruth} />
          <SectionBlock title="Recommended actions" body={structuredSummary.actions} />
          <SectionBlock title="Information gaps" body={structuredSummary.gaps} />
          <SectionBlock title="Incident suggestion" body={structuredSummary.incidentSuggestion} />
        </>
      ) : (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Root cause</p>
          <p className="text-sm text-muted-foreground">
            {incident.rootCauseExplanation || incident.answer || incident.summary}
          </p>
        </div>
      )}
      {incident.impactSummary ? (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Impact summary</p>
          <p className="text-sm text-muted-foreground">{incident.impactSummary}</p>
        </div>
      ) : null}
      {incident.blastRadiusScore !== undefined ? (
        <p className="text-xs text-muted-foreground">
          Blast radius score · {Math.round(incident.blastRadiusScore)}
        </p>
      ) : null}
      {resolutionPlan.length ? (
        <div data-testid="incident-detail-resolution">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Recommended actions</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground">
            {resolutionPlan.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {divergence ? (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-xs uppercase tracking-wide text-amber-200">Evidence divergence</p>
          {divergence.summary ? (
            <p className="mt-2 text-sm text-amber-50">{divergence.summary}</p>
          ) : null}
          {divergenceItems.length ? (
            <ul className="mt-2 space-y-1 text-sm text-amber-50">
              {divergenceItems.slice(0, 4).map((item, idx) => (
                <li key={`${item.source1 ?? "sourceA"}-${item.source2 ?? "sourceB"}-${idx}`}>
                  <span className="font-semibold">{item.source1 || "Source A"}</span> vs{" "}
                  <span className="font-semibold">{item.source2 || "Source B"}</span>:{" "}
                  {item.description || "Conflict detected"}
                </li>
              ))}
              {typeof divergence.count === "number" && divergenceItems.length < divergence.count ? (
                <li className="text-xs text-amber-200/80">
                  +{divergence.count - divergenceItems.length} additional divergence
                  {divergence.count - divergenceItems.length === 1 ? "" : "s"}
                </li>
              ) : null}
            </ul>
          ) : null}
        </div>
      ) : null}
      {informationGaps.length ? (
        <div className="rounded-2xl border border-sky-500/30 bg-sky-500/5 p-4">
          <p className="text-xs uppercase tracking-wide text-sky-200">Information gaps</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-sky-50">
            {informationGaps.map((gap, idx) => (
              <li key={`${gap.description}-${idx}`}>
                {gap.description}
                {gap.type ? <span className="text-sky-200/80"> ({gap.type})</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SignalsPanel({
  incident,
  activitySignals,
  dissatisfactionSignals,
  activityScore,
  dissatisfactionScore,
}: {
  incident: IncidentRecord;
  activitySignals?: Record<string, number>;
  dissatisfactionSignals?: Record<string, number>;
  activityScore?: number;
  dissatisfactionScore?: number;
}) {
  const fallbackAggregated =
    activitySignals || dissatisfactionSignals ? undefined : aggregateEntitySignals(incident);
  const mergedActivitySignals =
    activitySignals ?? incident.activitySignals ?? fallbackAggregated?.activitySignals;
  const mergedDissatisfactionSignals =
    dissatisfactionSignals ?? incident.dissatisfactionSignals ?? fallbackAggregated?.dissatisfactionSignals;
  const hasSignals =
    (mergedActivitySignals && Object.keys(mergedActivitySignals).length > 0) ||
    (mergedDissatisfactionSignals && Object.keys(mergedDissatisfactionSignals).length > 0);
  const scoreCards = [
    { label: "Activity score", value: activityScore ?? incident.activityScore, tone: "emerald" },
    { label: "Dissatisfaction score", value: dissatisfactionScore ?? incident.dissatisfactionScore, tone: "rose" },
  ].filter((card) => typeof card.value === "number");

  return (
    <div
      className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5"
      data-testid="incident-detail-signals"
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Activity & dissatisfaction scores</h2>
          <p className="text-xs text-muted-foreground">
            Primary health metrics for this incident, derived from recent Git, Slack, support, and doc-issue signals.
          </p>
        </div>
      </div>
      {scoreCards.length ? (
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2">
          {scoreCards.map((card) => (
            <div
              key={card.label}
              className={cn(
                "rounded-3xl border-2 bg-background/80 p-4 shadow-inner",
                card.tone === "emerald"
                  ? "border-emerald-500/60 text-emerald-100"
                  : "border-rose-500/60 text-rose-100",
              )}
            >
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground/70">Final {card.label}</p>
              <p className="text-4xl font-semibold leading-tight">
                {(card.value as number).toFixed(1)}
                <span className="ml-1 text-sm font-normal text-muted-foreground/80">/ 100</span>
              </p>
              <p className="text-xs text-muted-foreground/80">
                Derived from the latest Git, Slack, support, and doc inputs.
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Final scores were not attached to this incident; review the signal inputs below.
        </p>
      )}
      {hasSignals ? (
        <>
          <div className="flex flex-wrap gap-2">
            {renderSignalChips(mergedActivitySignals, "activity")}
            {renderSignalChips(mergedDissatisfactionSignals, "dissatisfaction")}
          </div>
          <ScoreBreakdownExplanation
            incident={incident}
            activitySignals={mergedActivitySignals}
            dissatisfactionSignals={mergedDissatisfactionSignals}
            activityScore={activityScore}
            dissatisfactionScore={dissatisfactionScore}
          />
        </>
      ) : (
        <p className="text-sm text-muted-foreground">No signal metrics attached to this incident.</p>
      )}
    </div>
  );
}

function DependencyPanel({ incident }: { incident: IncidentRecord }) {
  const dependency = incident.dependencyImpact;
  const impacts = dependency?.impacts;
  const reason =
    dependency && typeof (dependency as any).reason === "string"
      ? ((dependency as any).reason as string)
      : undefined;
  if (!dependency || !Array.isArray(impacts) || impacts.length === 0) {
    return (
      <div
        className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5"
        data-testid="incident-detail-dependencies"
      >
        <h2 className="text-lg font-semibold text-foreground">Cross-system impact</h2>
        <p className="text-sm text-muted-foreground">
          {reason || "No dependent services were recorded for this incident or graph context was unavailable."}
        </p>
      </div>
    );
  }

  return (
    <div
      className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5"
      data-testid="incident-detail-dependencies"
    >
      <h2 className="text-lg font-semibold text-foreground">Cross-system impact</h2>
      {renderSummaryMetrics([
        { label: "Components", value: dependency.affectedComponents?.length },
        { label: "Docs", value: dependency.docsNeedingUpdates?.length },
        { label: "Services", value: dependency.servicesNeedingUpdates?.length },
      ])}
      <div className="space-y-2 text-sm">
        {impacts.map((impact, index) => (
          <div key={`${impact.componentId ?? index}`} className="rounded-2xl border border-border/60 bg-background/60 p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Upstream</p>
            <p className="text-sm font-semibold text-foreground">{impact.componentId || "Unknown component"}</p>
            <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
              {impact.severity ? <span>Severity {impact.severity}</span> : null}
              {typeof impact.depth === "number" ? <span>Depth {impact.depth}</span> : null}
            </div>
            {renderImpactList("Dependent components", impact.dependentComponents)}
            {renderImpactList("Docs to update", impact.docs)}
            {renderImpactList("Services", impact.services)}
            {renderImpactList("Exposed APIs", impact.exposedApis)}
          </div>
        ))}
      </div>
    </div>
  );
}

function GraphQueryPanel({ incident }: { incident: IncidentRecord }) {
  const entries = Object.entries(incident.graphQuery ?? {});
  const hasQueries = entries.length > 0;
  const hasAnyCypher = entries.some(([, metadata]) => {
    const meta = (metadata ?? {}) as Record<string, unknown>;
    return typeof meta.cypher === "string" && meta.cypher.length > 0;
  });

  return (
    <section className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Graph slices & Cypher</h2>
          <p className="text-xs text-muted-foreground">
            {hasQueries
              ? hasAnyCypher
                ? "Exact Neo4j queries used for this incident's dependency walk."
                : "Default graph neighborhood derived from impacted components, docs, and dependency impact."
              : "No Neo4j queries were attached to this incident yet."}
          </p>
        </div>
      </div>
      {hasQueries ? (
        <div className="space-y-4">
          {entries.map(([label, metadata]) => {
            const meta = metadata || {};
            const displayLabel = meta.label || label;
            return (
              <div key={label} className="space-y-2 rounded-2xl border border-border/60 bg-background/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">{displayLabel}</p>
                    {(() => {
                      const snakeRowCount = (meta as Record<string, unknown>)["row_count"];
                      const rowCount = Number.isFinite(meta.rowCount)
                        ? Number(meta.rowCount)
                        : typeof snakeRowCount === "number"
                          ? (snakeRowCount as number)
                          : undefined;
                      return (
                        <p className="text-xs text-muted-foreground">
                          {meta.database ? `${meta.database} · ` : ""}
                          {typeof rowCount === "number" ? `${rowCount} ${rowCount === 1 ? "row" : "rows"}` : "Query"}
                        </p>
                      );
                    })()}
                  </div>
                  {meta.cypher ? (
                    <AskCerebrosCopyButton command={meta.cypher} label="Copy Cypher" size="sm" variant="outline" />
                  ) : null}
                </div>
                {(() => {
                  const cypherText =
                    typeof meta.cypher === "string" && meta.cypher.trim().length
                      ? meta.cypher
                      : DEFAULT_GRAPH_CYPHER;
                  const isFallback = cypherText === DEFAULT_GRAPH_CYPHER && (!meta.cypher || !meta.cypher.trim());
                  return (
                    <div className="space-y-1">
                      <pre className="overflow-auto rounded-2xl border border-border/50 bg-black/60 p-3 font-mono text-xs text-emerald-100">
                        <code>{cypherText}</code>
                      </pre>
                      {isFallback ? (
                        <p className="text-[11px] text-muted-foreground">
                          Default Cypher shown because the original slice omitted query text.
                        </p>
                      ) : null}
                    </div>
                  );
                })()}
                {meta.params ? (
                  <details className="rounded-2xl border border-border/60 bg-background/50 p-3 text-xs text-muted-foreground">
                    <summary className="cursor-pointer text-foreground">Parameters</summary>
                    <pre className="mt-2 overflow-auto text-[11px]">{JSON.stringify(meta.params, null, 2)}</pre>
                  </details>
                ) : null}
                {meta.error ? <p className="text-xs text-amber-500">Neo4j reported: {meta.error}</p> : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Add a graph query to this incident to reproduce the dependency walk in Neo4j.
        </p>
      )}
    </section>
  );
}

function EvidencePanel({
  docPriorities,
  evidenceItems,
  brainTraceHref,
  brainUniverseHref,
}: {
  docPriorities: Array<Record<string, unknown>>;
  evidenceItems: InvestigationEvidence[];
  brainTraceHref?: string;
  brainUniverseHref?: string;
}) {
  const linkedEvidence = useMemo(
    () => evidenceItems.filter((evidence) => Boolean(resolveEvidenceHref(evidence))),
    [evidenceItems],
  );
  const hasDocPriorities = docPriorities.length > 0;
  const hasEvidence = linkedEvidence.length > 0;

  return (
    <div className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Evidence & links</h2>
          <p className="text-xs text-muted-foreground">Doc priorities flagged by Cerebros</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {brainTraceHref ? (
            <Button asChild variant="outline" size="sm" className="rounded-full text-xs">
              <Link href={brainTraceHref} target="_blank" rel="noreferrer">
                Brain trace
              </Link>
            </Button>
          ) : null}
          {brainUniverseHref ? (
            <Button asChild variant="outline" size="sm" className="rounded-full text-xs">
              <Link href={brainUniverseHref} target="_blank" rel="noreferrer">
                Brain universe
              </Link>
            </Button>
          ) : null}
        </div>
      </div>
      {hasDocPriorities ? (
        <div className="space-y-3">
          {docPriorities.map((priority, index) => {
            const docTitle =
              typeof priority["doc_title"] === "string" ? (priority["doc_title"] as string) : undefined;
            const docId = typeof priority["doc_id"] === "string" ? (priority["doc_id"] as string) : undefined;
            const docPath =
              typeof priority["doc_path"] === "string" ? (priority["doc_path"] as string) : undefined;
            const docUrl = typeof priority["doc_url"] === "string" ? (priority["doc_url"] as string) : undefined;
            const reason = typeof priority["reason"] === "string" ? (priority["reason"] as string) : undefined;
            const docHref =
              buildDocLink(docUrl, docPath ?? docId ?? docTitle) ??
              buildDocLink(docUrl, docUrl);
            return (
              <div key={docId ?? docTitle ?? index} className="rounded-2xl border border-border/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{docTitle || docId || "Documentation"}</p>
                    <p className="text-xs text-muted-foreground">{reason || "Flagged by Cerebros"}</p>
                  </div>
                  {docHref ? (
                    <Button asChild variant="outline" size="sm" className="rounded-full text-xs">
                      <Link href={docHref} target="_blank" rel="noreferrer">
                        View doc ↗
                      </Link>
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Doc priorities and evidence will appear once linked.</p>
      )}
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Multi-source evidence</p>
        {hasEvidence ? (
          <div className="space-y-2">
            {linkedEvidence.map((evidence, index) => {
              const anchorId = getEvidenceAnchorId(String(evidence.evidenceId ?? evidence.title ?? index), index);
              const evidenceHref = resolveEvidenceHref(evidence);
              return (
                <div
                  key={evidence.evidenceId ?? evidence.title ?? index}
                  id={anchorId}
                  className="rounded-2xl border border-border/60 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        {evidence.source ? evidence.source.toUpperCase() : "Evidence"}
                      </p>
                      <p className="text-sm font-semibold text-foreground">{evidence.title || "Evidence item"}</p>
                    </div>
                    {evidenceHref ? (
                      <Button asChild variant="outline" size="sm" className="rounded-full text-xs">
                        <Link href={evidenceHref} target="_blank" rel="noreferrer">
                          Open ↗
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No multi-source evidence captured yet.</p>
        )}
      </div>
    </div>
  );
}

type SeverityRow = {
  key: string;
  label: string;
  score?: string;
  weight?: string;
  contribution?: string;
  note?: string;
};

type SeverityRowContext = {
  details?: SeverityDetailsPayload;
  semanticPairs?: Record<string, SeveritySemanticPair>;
};

type SeverityRowConfig = {
  key: string;
  label: string;
  hideWeight?: boolean;
  hideContribution?: boolean;
  note?: (ctx: SeverityRowContext) => string | undefined;
};

function buildSeverityRows({
  breakdown,
  weights,
  contributions,
  details,
  semanticPairs,
}: {
  breakdown?: Record<string, number>;
  weights?: Record<string, number>;
  contributions?: Record<string, number>;
  details?: SeverityDetailsPayload;
  semanticPairs?: Record<string, SeveritySemanticPair>;
}): SeverityRow[] {
  const configs: SeverityRowConfig[] = [
    { key: "slack", label: "Slack signals", note: (ctx) => formatSlackSeverity(ctx.details?.slack) },
    { key: "git", label: "Git + doc changes", note: (ctx) => formatGitSeverity(ctx.details?.git) },
    { key: "doc", label: "Doc issue health", note: (ctx) => formatDocSeverity(ctx.details?.doc) },
    {
      key: "semantic",
      label: "Semantic drift",
      note: (ctx) => formatSemanticSummary(ctx.semanticPairs),
    },
    { key: "graph", label: "Blast radius", note: (ctx) => formatGraphSeverity(ctx.details?.graph) },
    {
      key: "syntactic",
      label: "Syntactic (avg)",
      hideWeight: true,
      hideContribution: true,
      note: () => "Average of Slack, Git, and Doc heuristics",
    },
    {
      key: "relationship",
      label: "Relationship / graph",
      hideWeight: true,
      hideContribution: true,
      note: (ctx) => formatGraphSeverity(ctx.details?.graph),
    },
  ];

  return configs
    .map((config) => {
      const rawScore = breakdown?.[config.key];
      if (typeof rawScore !== "number") {
        return null;
      }
      const row: SeverityRow = {
        key: config.key,
        label: config.label,
        score: asPercent(rawScore),
        weight: config.hideWeight ? undefined : asPercent(weights?.[config.key]),
        contribution: config.hideContribution ? undefined : asPercent(contributions?.[config.key]),
        note: config.note ? config.note({ details, semanticPairs }) : undefined,
      };
      return row;
    })
    .filter((row): row is SeverityRow => Boolean(row));
}

function asPercent(value?: number, digits = 0): string | undefined {
  if (typeof value !== "number") {
    return undefined;
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function formatSlackSeverity(details?: Record<string, unknown>): string | undefined {
  if (!details) return undefined;
  const slack = details as Record<string, unknown>;
  const parts: string[] = [];
  const msgs = Number(slack.msg_count_7d);
  if (Number.isFinite(msgs) && msgs > 0) parts.push(`${msgs} msgs`);
  const threads = Number(slack.thread_count_7d);
  if (Number.isFinite(threads) && threads > 0) parts.push(`${threads} threads`);
  const authors = Number(slack.unique_authors_7d);
  if (Number.isFinite(authors) && authors > 0) parts.push(`${authors} authors`);
  if (slack.in_critical_channels) {
    parts.push("critical channel");
  }
  return parts.length ? parts.join(" · ") : undefined;
}

function formatGitSeverity(details?: Record<string, unknown>): string | undefined {
  if (!details) return undefined;
  const git = details as Record<string, unknown>;
  const parts: string[] = [];
  const prs = Number(git.pr_count_7d);
  if (Number.isFinite(prs) && prs > 0) parts.push(`${prs} PRs`);
  const commits = Number(git.commit_count_7d);
  if (Number.isFinite(commits) && commits > 0) parts.push(`${commits} commits`);
  const docs = Number(git.doc_change_count_7d);
  if (Number.isFinite(docs) && docs > 0) parts.push(`${docs} doc edits`);
  const breaking = Number(git.breaking_label_count_7d);
  if (Number.isFinite(breaking) && breaking > 0) parts.push(`${breaking} breaking labels`);
  return parts.length ? parts.join(" · ") : undefined;
}

function formatDocSeverity(details?: Record<string, unknown>): string | undefined {
  if (!details) return undefined;
  const doc = details as Record<string, unknown>;
  const parts: string[] = [];
  const base = typeof doc.base_severity_score === "number" ? doc.base_severity_score.toFixed(2) : undefined;
  const impact = typeof doc.impact_level_score === "number" ? doc.impact_level_score.toFixed(2) : undefined;
  if (base) parts.push(`base ${base}`);
  if (impact) parts.push(`impact ${impact}`);
  const components = Number(doc.component_count);
  if (Number.isFinite(components) && components > 0) parts.push(`${components} components`);
  if (Array.isArray(doc.labels) && doc.labels.length) {
    parts.push((doc.labels as string[]).slice(0, 3).join(", "));
  }
  const updatedAt = typeof doc.updated_at === "string" ? new Date(doc.updated_at) : null;
  if (updatedAt && !Number.isNaN(updatedAt.getTime())) {
    parts.push(`updated ${updatedAt.toLocaleDateString()}`);
  }
  return parts.length ? parts.join(" · ") : undefined;
}

function formatGraphSeverity(details?: Record<string, unknown>): string | undefined {
  if (!details) return undefined;
  const graph = details as Record<string, unknown>;
  const parts: string[] = [];
  const components = Number(graph.num_components);
  if (Number.isFinite(components) && components > 0) parts.push(`${components} components`);
  const docs = Number(graph.num_docs);
  if (Number.isFinite(docs) && docs > 0) parts.push(`${docs} docs`);
  const services = Number(graph.num_services);
  if (Number.isFinite(services) && services > 0) parts.push(`${services} services`);
  const downstream = Number(graph.downstream_components_depth2);
  if (Number.isFinite(downstream) && downstream > 0) parts.push(`${downstream} downstream`);
  const slackSignals = Number(graph.num_activity_signals_7d_slack);
  if (Number.isFinite(slackSignals) && slackSignals > 0) parts.push(`${slackSignals} slack signals`);
  const gitSignals = Number(graph.num_activity_signals_7d_git);
  if (Number.isFinite(gitSignals) && gitSignals > 0) parts.push(`${gitSignals} git signals`);
  const supportCases = Number(graph.num_support_cases);
  if (Number.isFinite(supportCases) && supportCases > 0) parts.push(`${supportCases} support cases`);
  return parts.length ? parts.join(" · ") : undefined;
}

function formatSemanticSummary(pairs?: Record<string, SeveritySemanticPair>): string | undefined {
  if (!pairs || !Object.keys(pairs).length) {
    return undefined;
  }
  const sorted = Object.entries(pairs).sort((a, b) => (b[1]?.drift ?? 0) - (a[1]?.drift ?? 0));
  const [pairKey, meta] = sorted[0];
  if (!meta || typeof meta.drift !== "number") {
    return undefined;
  }
  const driftPercent = (meta.drift * 100).toFixed(1);
  const cosine = typeof meta.cosine === "number" ? meta.cosine.toFixed(3) : "n/a";
  return `${formatSemanticLabel(pairKey)} drift ${driftPercent}% (cosine ${cosine})`;
}

function formatSemanticLabel(key: string): string {
  switch (key) {
    case "doc_vs_slack":
      return "Docs vs Slack";
    case "doc_vs_git":
      return "Docs vs Git";
    case "doc_vs_api":
      return "Docs vs API";
    default:
      return key.replace(/_/g, " ");
  }
}

function renderSignalChips(
  signals: IncidentRecord["activitySignals"],
  variant: "activity" | "dissatisfaction",
) {
  if (!signals) return null;
  const seen = new Set<string>();
  return Object.entries(signals)
    .filter(([, value]) => typeof value === "number" && value > 0)
    .map(([key, value]) => {
      const normalized = key.toLowerCase();
      if (seen.has(normalized)) {
        return null;
      }
      seen.add(normalized);
      return (
        <span
          key={`${variant}-${key}`}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
            variant === "activity" ? "border-emerald-500/40 text-emerald-200" : "border-rose-500/40 text-rose-200",
          )}
        >
          {key.replace(/_/g, " ")} <span className="font-bold">{value}</span>
        </span>
      );
    });
}

function renderSummaryMetrics(
  metrics: Array<{ label: string; value?: number }>,
) {
  const filtered = metrics.filter((metric) => typeof metric.value === "number" && metric.value !== undefined);
  if (!filtered.length) {
    return null;
  }
  return (
    <div className="grid grid-cols-3 gap-3 text-center text-xs">
      {filtered.map((metric) => (
        <div key={metric.label} className="rounded-2xl border border-border/60 bg-background/60 p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{metric.label}</p>
          <p className="text-lg font-semibold text-foreground">{metric.value}</p>
        </div>
      ))}
    </div>
  );
}

function renderImpactList(label: string, items?: string[]) {
  if (!items || items.length === 0) {
    return null;
  }
  return (
    <div className="space-y-1">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-1">
        {items.map((item) => (
          <span
            key={`${label}-${item}`}
            className="rounded-full border border-border/60 bg-background/70 px-2 py-0.5 text-[11px] text-foreground"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function ScoreBreakdownExplanation({
  incident,
  activitySignals,
  dissatisfactionSignals,
  activityScore,
  dissatisfactionScore,
}: {
  incident: IncidentRecord;
  activitySignals?: Record<string, number>;
  dissatisfactionSignals?: Record<string, number>;
  activityScore?: number;
  dissatisfactionScore?: number;
}) {
  const activity = activitySignals ?? {};
  const dissatisfaction = dissatisfactionSignals ?? {};

  const gitEvents = typeof activity.git_events === "number" ? activity.git_events : undefined;
  const slackThreads = typeof activity.slack_threads === "number" ? activity.slack_threads : undefined;
  const docIssuesActivity =
    typeof activity.doc_issues === "number" ? activity.doc_issues : undefined;

  const slackComplaints =
    typeof dissatisfaction.slack_complaints === "number" ? dissatisfaction.slack_complaints : undefined;
  const criticalDocIssues =
    typeof dissatisfaction.critical_doc_issues === "number" ? dissatisfaction.critical_doc_issues : undefined;
  const docIssuesDiss =
    typeof dissatisfaction.doc_issues === "number" ? dissatisfaction.doc_issues : undefined;

  const hasAnyInputs =
    gitEvents ||
    slackThreads ||
    docIssuesActivity ||
    slackComplaints ||
    criticalDocIssues ||
    docIssuesDiss;

  return (
    <details className="mt-2 space-y-2 rounded-2xl border border-border/60 bg-background/60 p-3 text-[11px] text-muted-foreground/90">
      <summary className="cursor-pointer text-xs font-semibold text-foreground">
        How we calculate these scores
      </summary>
      <p>
        At incident time we reuse the component activity graph and, when needed, fall back to a simple transparent
        formula. The high-level rules are:
      </p>
      <ul className="ml-4 list-disc space-y-1">
        <li>
          <span className="font-semibold text-foreground">Activity score</span>{" "}
          uses the graph&apos;s component activity score when available; otherwise it falls back to{" "}
          <code className="rounded bg-border/40 px-1 py-0.5">
            0.8 × git_events + 0.4 × slack_threads + 0.2 × doc_pressure
          </code>
          .
        </li>
        <li>
          <span className="font-semibold text-foreground">Dissatisfaction score</span>{" "}
          uses the graph&apos;s dissatisfaction score when available; otherwise it falls back to{" "}
          <code className="rounded bg-border/40 px-1 py-0.5">
            0.9 × slack_complaints + 1.0 × doc_pressure
          </code>{" "}
          with a small floor so pure doc-drift still shows non-zero dissatisfaction.
        </li>
      </ul>
      {hasAnyInputs ? (
        <div className="space-y-2">
          <p className="font-semibold text-foreground">Signals feeding this incident</p>
          <div className="grid gap-2 md:grid-cols-2">
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Activity inputs</p>
              <dl className="space-y-0.5">
                <ScoreInputRow label="Git events" value={gitEvents} description="Recent Git events touching this component" />
                <ScoreInputRow
                  label="Slack threads"
                  value={slackThreads}
                  description="Slack conversations about this component"
                />
                <ScoreInputRow
                  label="Doc issues (pressure proxy)"
                  value={docIssuesActivity}
                  description="Number of open doc issues contributing to doc_pressure"
                />
              </dl>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Dissatisfaction inputs</p>
              <dl className="space-y-0.5">
                <ScoreInputRow
                  label="Slack complaints"
                  value={slackComplaints}
                  description="Slack complaint events tagged against this component"
                />
                <ScoreInputRow
                  label="Critical doc issues"
                  value={criticalDocIssues}
                  description="High / critical severity doc issues"
                />
                <ScoreInputRow
                  label="Total doc issues"
                  value={docIssuesDiss}
                  description="All open doc issues contributing to doc_pressure"
                />
              </dl>
            </div>
          </div>
      <p className="text-[10px] text-muted-foreground/80">
        Final incident-level scores shown above are either taken directly from the component&apos;s activity graph (
        {formatScoreLabel(activityScore ?? incident.activityScore, "activity")},{" "}
        {formatScoreLabel(dissatisfactionScore ?? incident.dissatisfactionScore, "dissatisfaction")}) or computed from
        the fallback formulas using these inputs.
      </p>
        </div>
      ) : null}
    </details>
  );
}

function ScoreInputRow({
  label,
  value,
  description,
}: {
  label: string;
  value?: number;
  description: string;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className="w-28 text-[11px] text-muted-foreground">{label}</dt>
      <dd className="text-[11px] text-foreground">
        {typeof value === "number" ? value : "—"}
        <span className="ml-1 text-[10px] text-muted-foreground/80">{description}</span>
      </dd>
    </div>
  );
}

function resolveActivityScore(
  explicitScore?: number,
  activitySignals?: Record<string, number>,
): number | undefined {
  if (isFiniteNumber(explicitScore)) {
    return explicitScore;
  }
  return computeActivityFallback(activitySignals);
}

function resolveDissatisfactionScore(
  explicitScore?: number,
  activitySignals?: Record<string, number>,
  dissatisfactionSignals?: Record<string, number>,
): number | undefined {
  if (isFiniteNumber(explicitScore)) {
    return explicitScore;
  }
  return computeDissatisfactionFallback(activitySignals, dissatisfactionSignals);
}

function computeActivityFallback(activitySignals?: Record<string, number>): number | undefined {
  if (!activitySignals) return undefined;
  const gitEvents = readSignalValue(activitySignals, ["git_events", "git_activity"], (key) => key.includes("git"));
  const slackThreads = readSignalValue(activitySignals, ["slack_threads"], (key) => key.includes("slack"));
  const docPressure = readSignalValue(
    activitySignals,
    ["doc_pressure", "doc_issues", "doc_priority"],
    (key) => key.includes("doc"),
  );
  const fallback =
    (gitEvents ?? 0) * 0.8 + (slackThreads ?? 0) * 0.4 + (docPressure ?? 0) * 0.2;
  return fallback > 0 ? clampScore(fallback) : undefined;
}

function computeDissatisfactionFallback(
  activitySignals?: Record<string, number>,
  dissatisfactionSignals?: Record<string, number>,
): number | undefined {
  const slackComplaints = readSignalValue(
    dissatisfactionSignals,
    ["slack_complaints", "support_cases", "ticket_complaints"],
    (key) => key.includes("slack") || key.includes("support"),
  );
  const docPressure =
    readSignalValue(dissatisfactionSignals, ["doc_pressure", "doc_issues"], (key) => key.includes("doc")) ??
    readSignalValue(activitySignals, ["doc_pressure", "doc_issues", "doc_priority"], (key) => key.includes("doc"));
  const fallback = (slackComplaints ?? 0) * 0.9 + (docPressure ?? 0);
  let adjusted = fallback;
  if ((!slackComplaints || slackComplaints <= 0) && docPressure && docPressure > 0) {
    adjusted = Math.max(adjusted, Math.min(docPressure, 1));
  }
  return adjusted > 0 ? clampScore(adjusted) : undefined;
}

function readSignalValue(
  signals: Record<string, number> | undefined,
  candidateKeys: string[],
  fallbackMatcher?: (key: string) => boolean,
): number | undefined {
  if (!signals) return undefined;
  for (const key of candidateKeys) {
    const value = signals[key];
    if (isFiniteNumber(value)) {
      return value;
    }
  }
  if (fallbackMatcher) {
    let total = 0;
    for (const [key, value] of Object.entries(signals)) {
      if (!fallbackMatcher(key)) continue;
      if (!isFiniteNumber(value)) continue;
      total += value;
    }
    if (total > 0) {
      return total;
    }
  }
  return undefined;
}

function clampScore(value: number): number {
  return Number(Math.max(0, Math.min(100, value)).toFixed(1));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatScoreLabel(value: number | undefined, label: string): string {
  return typeof value === "number" ? `${label} ${value.toFixed(1)}` : `${label} n/a`;
}

function aggregateEntitySignals(incident: IncidentRecord): {
  activitySignals?: Record<string, number>;
  dissatisfactionSignals?: Record<string, number>;
} {
  const entities = incident.incidentEntities ?? [];
  if (!entities.length) {
    return {};
  }
  const activity: Record<string, number> = {};
  const dissatisfaction: Record<string, number> = {};

  for (const entity of entities) {
    const act = entity.activitySignals ?? {};
    const diss = entity.dissatisfactionSignals ?? {};
    for (const [key, raw] of Object.entries(act)) {
      const value = typeof raw === "number" ? raw : Number(raw);
      if (!Number.isFinite(value) || value <= 0) continue;
      activity[key] = (activity[key] ?? 0) + value;
    }
    for (const [key, raw] of Object.entries(diss)) {
      const value = typeof raw === "number" ? raw : Number(raw);
      if (!Number.isFinite(value) || value <= 0) continue;
      dissatisfaction[key] = (dissatisfaction[key] ?? 0) + value;
    }
  }

  return {
    activitySignals: Object.keys(activity).length ? activity : undefined,
    dissatisfactionSignals: Object.keys(dissatisfaction).length ? dissatisfaction : undefined,
  };
}

function SectionBlock({ title, body }: { title: string; body?: string | null }) {
  if (!body) return null;
  return (
    <div className="space-y-1">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{title}</p>
      <p className="whitespace-pre-line text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

function parseStructuredSummary(text: string | null): {
  sourceEvidence?: string;
  drift?: string;
  canonicalTruth?: string;
  actions?: string;
  gaps?: string;
  incidentSuggestion?: string;
} | null {
  if (!text) return null;
  const sections: Record<string, string> = {};
  const headings = [
    "SOURCE EVIDENCE:",
    "DRIFT:",
    "CANONICAL CURRENT TRUTH:",
    "ACTIONS:",
    "GAPS:",
    "INCIDENT SUGGESTION:",
  ];
  let current: string | null = null;
  const lines = text.split("\n");
  for (const rawLine of lines) {
    const line = rawLine.trim();
    const heading = headings.find((h) => line.startsWith(h));
    if (heading) {
      current = heading;
      sections[heading] = line.slice(heading.length).trim();
      continue;
    }
    if (!current) continue;
    sections[current] = sections[current]
      ? `${sections[current]}\n${line}`
      : line;
  }
  if (Object.keys(sections).length === 0) {
    return null;
  }
  return {
    sourceEvidence: sections["SOURCE EVIDENCE:"],
    drift: sections["DRIFT:"],
    canonicalTruth: sections["CANONICAL CURRENT TRUTH:"],
    actions: sections["ACTIONS:"],
    gaps: sections["GAPS:"],
    incidentSuggestion: sections["INCIDENT SUGGESTION:"],
  };
}

function deriveIncidentTitle(incident: IncidentRecord): string {
  if (incident.question && incident.question.trim()) {
    return incident.question.trim();
  }
  const summary = incident.summary || incident.rootCauseExplanation || incident.answer;
  if (!summary) {
    return "Incident";
  }
  const firstSentence = summary.split(/(?<=[.!?])\s+/)[0]?.trim();
  if (firstSentence && firstSentence.length <= 140) {
    return firstSentence;
  }
  return summary.slice(0, 140).trimEnd() + (summary.length > 140 ? "…" : "");
}

function deriveIncidentSummary(incident: IncidentRecord): string | null {
  const summary = incident.summary || incident.answer || incident.rootCauseExplanation;
  if (!summary) {
    return null;
  }
  return summary.trim();
}

