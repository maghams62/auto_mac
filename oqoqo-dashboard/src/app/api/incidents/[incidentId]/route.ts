import {
  findTraceabilityIncidentById,
  getTraceabilitySourcePath,
  type TraceabilityIncident,
} from "@/app/api/incidents/traceability-store";
import { jsonOk } from "@/lib/server/api-response";
import type {
  GraphQueryMetadata,
  IncidentEntity,
  IncidentRecord,
  InvestigationEvidence,
  SeverityDetailsPayload,
  SeveritySemanticPair,
  SeverityExplanation,
} from "@/lib/types";

const DEFAULT_GRAPH_CYPHER = "MATCH (n) RETURN n LIMIT 25";

export async function GET(
  _request: Request,
  context: { params: Promise<{ incidentId: string }> } | { params: { incidentId: string } },
) {
  const params = "then" in context.params ? await context.params : context.params;
  const incidentId = params.incidentId;
  let dependencies: Record<string, unknown> = { traceabilityStore: { path: getTraceabilitySourcePath() } };

  const { incident, meta } = await findTraceabilityIncidentById(incidentId);
  dependencies = { traceabilityStore: meta };

  if (!incident) {
    console.warn("[incidents/:id] incident not found in traceability log", {
      incidentId,
      path: meta.path,
    });
    return jsonOk({
      status: "NOT_FOUND",
      data: null,
      dependencies,
      error: {
        type: "NOT_FOUND",
        message: "Incident not found",
      },
    });
  }

  return jsonOk({
    status: "OK",
    data: { incident: mapIncidentRecord(incident) },
    dependencies,
  });
}

function mapIncidentRecord(record: TraceabilityIncident): IncidentRecord {
  const summaryFallback = record.summary || record.question || "Untitled incident";
  const candidateSnapshot = (record.metadata?.incident_candidate_snapshot ??
    {}) as Record<string, unknown>;
  const resolutionPlan = normalizeResolutionPlan(
    record.resolution_plan ?? candidateSnapshot?.resolution_plan,
  );
  const docPriorities =
    (record.doc_priorities as Array<Record<string, any>>) ||
    (candidateSnapshot?.doc_priorities as Array<Record<string, any>>) ||
    [];
  const snapshotEvidence = candidateSnapshot?.evidence as unknown;
  const rawEvidence =
    (record.evidence as unknown) ?? (Array.isArray(snapshotEvidence) ? snapshotEvidence : undefined);
  const evidence = normalizeEvidenceList(rawEvidence);
  const snapshotBrainTrace =
    (candidateSnapshot?.brainTraceUrl as string | undefined) ??
    (candidateSnapshot?.brain_trace_url as string | undefined);
  const snapshotBrainUniverse =
    (candidateSnapshot?.brainUniverseUrl as string | undefined) ??
    (candidateSnapshot?.brain_universe_url as string | undefined);
  const brainTraceUrl =
    (record.brainTraceUrl as string | undefined) ??
    snapshotBrainTrace ??
    (record.raw_trace_id ? `/brain/trace/${record.raw_trace_id}` : undefined);
  const brainUniverseUrl =
    (record.brainUniverseUrl as string | undefined) ?? snapshotBrainUniverse ?? "/brain/universe";
  const sourceDivergence =
    (record.source_divergence as IncidentRecord["sourceDivergence"]) ??
    (candidateSnapshot?.source_divergence as IncidentRecord["sourceDivergence"]);
  const informationGaps = normalizeInformationGaps(
    record.information_gaps ?? candidateSnapshot?.information_gaps,
  );
  const rawGraphQuery =
    (record.graph_query as Record<string, unknown> | undefined) ??
    (candidateSnapshot?.graph_query as Record<string, unknown> | undefined);
  const normalizedGraphQuery = normalizeGraphQuery(rawGraphQuery);
  const graphQuery =
    normalizedGraphQuery ?? buildDefaultGraphQuery(record);

  return {
    id: record.id ?? "incident",
    type: (record.type as IncidentRecord["type"]) ?? "incident",
    summary: summaryFallback,
    question: record.question,
    answer: record.answer,
    llmExplanation: (record.llm_explanation as string | undefined) ?? candidateSnapshot?.llm_explanation,
    severity: ((record.severity || "medium") as IncidentRecord["severity"]),
    status: ((record.status || "open") as IncidentRecord["status"]),
    blastRadiusScore: record.blast_radius_score,
    sourceCommand: record.source_command,
    rawTraceId: record.raw_trace_id,
    projectId: record.project_id,
    componentIds: record.component_ids ?? [],
    createdAt: record.created_at ?? new Date().toISOString(),
    counts: record.incident_context?.counts,
    incidentScope: record.incident_context?.impacted_nodes,
    recencyInfo: record.incident_context?.recency_info,
    rootCauseExplanation:
      (record.root_cause_explanation as string | undefined) ??
      (candidateSnapshot?.root_cause_explanation as string | undefined),
    impactSummary:
      (record.impact_summary as string | undefined) ??
      (candidateSnapshot?.impact_summary as string | undefined),
    resolutionPlan,
    activitySignals:
      (record.activity_signals as Record<string, number> | undefined) ??
      (candidateSnapshot?.activity_signals as Record<string, number> | undefined),
    dissatisfactionSignals:
      (record.dissatisfaction_signals as Record<string, number> | undefined) ??
      (candidateSnapshot?.dissatisfaction_signals as Record<string, number> | undefined),
    dependencyImpact:
      (record.dependency_impact as IncidentRecord["dependencyImpact"]) ??
      (candidateSnapshot?.dependency_impact as IncidentRecord["dependencyImpact"]),
    activityScore:
      (typeof record.activity_score === "number" ? record.activity_score : undefined) ??
      (typeof candidateSnapshot?.activity_score === "number"
        ? (candidateSnapshot.activity_score as number)
        : undefined),
    dissatisfactionScore:
      (typeof record.dissatisfaction_score === "number" ? record.dissatisfaction_score : undefined) ??
      (typeof candidateSnapshot?.dissatisfaction_score === "number"
        ? (candidateSnapshot.dissatisfaction_score as number)
        : undefined),
    graphQuery,
    docPriorities,
    sourceDivergence,
    informationGaps,
    metadata: record.metadata,
    brainTraceUrl,
    brainUniverseUrl,
    evidence: evidence ?? [],
    incidentEntities: normalizeIncidentEntities(
      record.incident_entities ?? candidateSnapshot?.incident_entities,
    ),
    severityScore:
      typeof record.severity_score === "number"
        ? record.severity_score
        : typeof candidateSnapshot?.severity_score === "number"
          ? (candidateSnapshot.severity_score as number)
          : undefined,
    severityScore100:
      typeof record.severity_score_100 === "number"
        ? record.severity_score_100
        : typeof candidateSnapshot?.severity_score_100 === "number"
          ? (candidateSnapshot.severity_score_100 as number)
          : undefined,
    severityBreakdown:
      (record.severity_breakdown as Record<string, number> | undefined) ??
      (candidateSnapshot?.severity_breakdown as Record<string, number> | undefined),
    severityDetails:
      (record.severity_details as SeverityDetailsPayload | undefined) ??
      (candidateSnapshot?.severity_details as SeverityDetailsPayload | undefined),
    severityContributions:
      (record.severity_contributions as Record<string, number> | undefined) ??
      (candidateSnapshot?.severity_contributions as Record<string, number> | undefined),
    severityWeights:
      (record.severity_weights as Record<string, number> | undefined) ??
      (candidateSnapshot?.severity_weights as Record<string, number> | undefined),
    severitySemanticPairs:
      (record.severity_semantic_pairs as Record<string, SeveritySemanticPair> | undefined) ??
      (candidateSnapshot?.severity_semantic_pairs as Record<string, SeveritySemanticPair> | undefined),
    severityExplanation:
      (record.severity_explanation as SeverityExplanation | undefined) ??
      (candidateSnapshot?.severity_explanation as SeverityExplanation | undefined),
  };
}

function normalizeResolutionPlan(value: unknown): string[] | undefined {
  if (!value) return undefined;
  if (Array.isArray(value)) {
    const normalized = value
      .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
      .filter(Boolean);
    return normalized.length ? normalized : undefined;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed) {
      return [trimmed];
    }
  }
  return undefined;
}

function normalizeGraphQuery(value: unknown): IncidentRecord["graphQuery"] {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const entries: Array<[string, GraphQueryMetadata]> = [];
  for (const [label, raw] of Object.entries(value as Record<string, unknown>)) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const meta = raw as Record<string, any>;
    const params = meta.params && typeof meta.params === "object" ? (meta.params as Record<string, unknown>) : undefined;
    const database =
      typeof meta.database === "string" || meta.database === null ? (meta.database as string | null) : undefined;
    const rowCount =
      typeof meta.rowCount === "number"
        ? meta.rowCount
        : typeof meta.row_count === "number"
          ? meta.row_count
          : undefined;
    const cypherText =
      typeof meta.cypher === "string" && meta.cypher.trim().length
        ? (meta.cypher as string)
        : DEFAULT_GRAPH_CYPHER;
    entries.push([
      label,
      {
        label: typeof meta.label === "string" ? meta.label : label,
        cypher: cypherText,
        params,
        database,
        rowCount,
        error: typeof meta.error === "string" ? meta.error : undefined,
      },
    ]);
  }
  if (!entries.length) {
    return undefined;
  }
  return Object.fromEntries(entries);
}

function buildDefaultGraphQuery(record: TraceabilityIncident): IncidentRecord["graphQuery"] {
  const context = (record.incident_context ?? {}) as {
    impacted_nodes?: {
      components?: unknown;
      doc_ids?: unknown;
    };
  };
  const scope = (context.impacted_nodes ?? {}) as {
    components?: unknown;
    doc_ids?: unknown;
  };
  const dependency = (record.dependency_impact ?? {}) as {
    servicesNeedingUpdates?: unknown;
    docsNeedingUpdates?: unknown;
    services?: unknown;
    docs?: unknown;
  };

  const countArray = (value: unknown): number =>
    Array.isArray(value) ? value.length : 0;

  const componentCount = countArray(scope.components);
  const docCount = countArray(scope.doc_ids);
  const dependencyServiceCount =
    countArray(dependency.servicesNeedingUpdates) + countArray(dependency.services);
  const dependencyDocCount =
    countArray(dependency.docsNeedingUpdates) + countArray(dependency.docs);

  const rowCount = componentCount + docCount + dependencyServiceCount + dependencyDocCount;
  if (!Number.isFinite(rowCount) || rowCount <= 0) {
    return undefined;
  }

  return {
    default: {
      label: "Default neighborhood",
      rowCount,
      cypher: DEFAULT_GRAPH_CYPHER,
    },
  };
}

function normalizeIncidentEntities(value: unknown): IncidentRecord["incidentEntities"] {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const rows: IncidentEntity[] = [];
  for (const entity of value) {
    if (!entity || typeof entity !== "object") {
      continue;
    }
    const payload = entity as Record<string, unknown>;
    const id = payload.id ?? payload.name;
    if (!id) {
      continue;
    }
    rows.push({
      id: String(id),
      name: String(payload.name ?? id),
      entityType: String(payload.entityType ?? "component"),
      activitySignals: normalizeSignalMap(payload.activitySignals),
      dissatisfactionSignals: normalizeSignalMap(payload.dissatisfactionSignals),
      docStatus: normalizeDocStatus(payload.docStatus),
      dependency: normalizeDependency(payload.dependency),
      suggestedAction: payload.suggestedAction ? String(payload.suggestedAction) : undefined,
      evidenceIds: Array.isArray(payload.evidenceIds)
        ? payload.evidenceIds.map((entry) => String(entry)).filter(Boolean)
        : undefined,
    });
  }
  return rows.length ? rows : undefined;
}

function normalizeInformationGaps(value: unknown): IncidentRecord["informationGaps"] {
  if (!Array.isArray(value)) return undefined;
  const normalized = value
    .map((entry) => {
      if (!entry || typeof entry !== "object") {
        return undefined;
      }
      const description = typeof (entry as any).description === "string" ? (entry as any).description.trim() : "";
      if (!description) {
        return undefined;
      }
      const type =
        typeof (entry as any).type === "string" && (entry as any).type.trim().length
          ? (entry as any).type.trim()
          : undefined;
      return { description, type };
    })
    .filter((item): item is { description: string; type?: string } => Boolean(item));
  return normalized.length ? normalized : undefined;
}

function normalizeEvidenceList(value: unknown): InvestigationEvidence[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const items: InvestigationEvidence[] = [];
  value.forEach((raw, index) => {
    if (!raw || typeof raw !== "object") {
      return;
    }
    const entry = raw as Record<string, unknown>;
    const evidenceId =
      entry.evidenceId ??
      entry.evidence_id ??
      entry.id ??
      entry.url ??
      `evidence-${index}`;
    const source = typeof entry.source === "string" ? (entry.source as string) : undefined;
    const title = typeof entry.title === "string" ? (entry.title as string) : undefined;
    const url = typeof entry.url === "string" ? (entry.url as string) : undefined;
    const metadata =
      entry.metadata && typeof entry.metadata === "object"
        ? (entry.metadata as Record<string, unknown>)
        : undefined;
    items.push({
      evidenceId: String(evidenceId),
      source,
      title,
      url,
      metadata,
    });
  });
  return items.length ? items : undefined;
}

function normalizeSignalMap(value: unknown): Record<string, number> | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const result: Record<string, number> = {};
  for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
    const numeric = Number(raw);
    if (!Number.isFinite(numeric)) {
      continue;
    }
    result[key] = numeric;
  }
  return Object.keys(result).length ? result : undefined;
}

function normalizeDocStatus(value: unknown) {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const payload = value as Record<string, unknown>;
  const status: Record<string, string> = {};
  if (payload.reason) status.reason = String(payload.reason);
  if (payload.status) status.status = String(payload.status);
  if (payload.severity) status.severity = String(payload.severity);
  return Object.keys(status).length ? status : undefined;
}

function normalizeDependency(value: unknown) {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const payload = value as Record<string, unknown>;
  const dependency: Record<string, unknown> = {};
  if (payload.componentId) dependency.componentId = String(payload.componentId);
  if (Array.isArray(payload.dependentComponents)) {
    dependency.dependentComponents = payload.dependentComponents.map((entry) => String(entry));
  }
  if (Array.isArray(payload.docs)) {
    dependency.docs = payload.docs.map((entry) => String(entry));
  }
  if (Array.isArray(payload.services)) {
    dependency.services = payload.services.map((entry) => String(entry));
  }
  if (Array.isArray(payload.exposedApis)) {
    dependency.exposedApis = payload.exposedApis.map((entry) => String(entry));
  }
  if (payload.depth !== undefined) {
    const depth = Number(payload.depth);
    if (Number.isFinite(depth)) dependency.depth = depth;
  }
  if (payload.severity) dependency.severity = String(payload.severity);
  return Object.keys(dependency).length ? dependency : undefined;
}

