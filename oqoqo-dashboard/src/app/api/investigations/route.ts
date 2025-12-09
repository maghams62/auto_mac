import { projects as mockProjects } from "@/lib/mock-data";
import { requestCerebrosJson } from "@/lib/clients/cerebros";
import type { ExternalResult } from "@/lib/clients/types";
import { parseLiveMode, resolveServerModeOverride } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import type { Investigation, InvestigationEvidence, LiveMode } from "@/lib/types";

type TraceabilityEvidence = {
  evidence_id?: string;
  source?: string;
  title?: string;
  url?: string;
  metadata?: Record<string, unknown>;
};

type TraceabilityToolRun = {
  step_id?: string;
  tool?: string;
  status?: string;
  output_preview?: string;
};

type TraceabilityInvestigation = {
  id?: string;
  question?: string;
  answer?: string;
  status?: string;
  goal?: string;
  plan_id?: string;
  session_id?: string;
  component_ids?: string[];
  created_at?: string;
  evidence?: TraceabilityEvidence[];
  tool_runs?: TraceabilityToolRun[];
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId") ?? undefined;
  const componentId = searchParams.get("componentId") ?? undefined;
  const since = searchParams.get("since") ?? undefined;
  const limit = Math.max(1, Math.min(parseInt(searchParams.get("limit") ?? "20", 10), 100));
  const forcedMode = parseLiveMode(searchParams.get("mode"));
  const syntheticRequested = forcedMode === "synthetic";

  const envMode = resolveServerModeOverride();
  let mode: LiveMode = syntheticRequested ? "synthetic" : envMode ?? "synthetic";
  let investigations: Investigation[] | null = null;
  let fallbackReason: string | undefined;
  const dependencies: Record<string, ExternalResult<unknown>> = {};

  if (!syntheticRequested) {
    const liveResult = await fetchInvestigations({ componentId, limit, since });
    dependencies.cerebrosInvestigations = liveResult;
    if (liveResult.status === "OK" && liveResult.data?.length) {
      investigations = liveResult.data.map((record) => mapTraceabilityInvestigation(record, projectId));
      mode = envMode ?? "atlas";
    } else {
      fallbackReason = "cerebros_unavailable";
    }
  }

  if (!investigations || investigations.length === 0) {
    investigations = fallbackInvestigations({ projectId, componentId, limit });
    mode = "synthetic";
    fallbackReason = fallbackReason ?? "synthetic_fallback";
  } else if (investigations.length > limit) {
    investigations = investigations.slice(0, limit);
  }

  return jsonOk({
    status: investigations.length ? "OK" : "UNAVAILABLE",
    mode,
    fallbackReason,
    data: investigations.length ? { investigations } : null,
    dependencies,
    error:
      investigations.length > 0
        ? undefined
        : {
            type: "UNKNOWN",
            message: "Investigations unavailable",
          },
  });
}

async function fetchInvestigations({
  componentId,
  limit,
  since,
}: {
  componentId?: string;
  limit: number;
  since?: string;
}): Promise<ExternalResult<TraceabilityInvestigation[]>> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (componentId) {
    params.set("component_id", componentId);
  }
  if (since) {
    const sinceIso = buildSinceIso(since);
    if (sinceIso) {
      params.set("since", sinceIso);
    }
  }

  const result = await requestCerebrosJson<{ investigations?: TraceabilityInvestigation[] }>(
    `/traceability/investigations?${params.toString()}`,
  );

  if (result.status !== "OK" || !result.data?.investigations) {
    return {
      status: result.status,
      data: null,
      error: result.error,
      meta: result.meta,
    };
  }

  return {
    status: "OK",
    data: result.data.investigations,
    meta: {
      provider: "cerebros",
      endpoint: "traceability/investigations",
    },
  };
}

function mapTraceabilityInvestigation(record: TraceabilityInvestigation, projectId?: string): Investigation {
  const sanitizedProjectId = projectId ?? "live";
  const componentIds = Array.isArray(record.component_ids) ? record.component_ids : [];
  const evidence = mapEvidence(record.evidence);
  const toolRuns =
    record.tool_runs?.map((run) => ({
      stepId: run.step_id,
      tool: run.tool ?? "unknown",
      status: run.status ?? "completed",
      outputPreview: run.output_preview,
    })) ?? [];

  return {
    id: record.id ?? `investigation:${Date.now()}`,
    projectId: sanitizedProjectId,
    sessionId: record.session_id,
    question: record.question ?? "Untitled investigation",
    answer: record.answer,
    status: record.status,
    goal: record.goal,
    planId: record.plan_id,
    createdAt: record.created_at ?? new Date().toISOString(),
    componentIds,
    evidence,
    toolRuns,
  };
}

function mapEvidence(evidence: TraceabilityEvidence[] | undefined): InvestigationEvidence[] {
  if (!Array.isArray(evidence)) return [];
  return evidence.map((entry) => ({
    evidenceId: entry.evidence_id ?? entry.url,
    source: entry.source,
    title: entry.title ?? entry.url ?? "Evidence",
    url: entry.url,
    metadata: entry.metadata,
  }));
}

function buildSinceIso(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  if (raw.includes("T")) {
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
  }
  const parsed = new Date(`${raw}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
}

function fallbackInvestigations({
  projectId,
  componentId,
  limit,
}: {
  projectId?: string;
  componentId?: string;
  limit: number;
}): Investigation[] {
  const projects = projectId ? mockProjects.filter((project) => project.id === projectId) : mockProjects;
  const synthetic = projects.flatMap((project) => {
    return project.docIssues.slice(0, limit).map((issue, idx) => ({
      id: `${issue.id}-investigation-${idx}`,
      projectId: project.id,
      question: `Why is ${issue.title} drifting?`,
      answer: issue.summary,
      status: issue.status,
      goal: "Doc drift triage",
      planId: undefined,
      sessionId: undefined,
      createdAt: issue.detectedAt,
      componentIds: [issue.componentId],
      evidence:
        issue.sourceLinks?.map((link) => ({
          evidenceId: link.url,
          source: link.type,
          title: link.label ?? link.url,
          url: link.url,
        })) ?? [],
      toolRuns: [
        {
          stepId: "slash-slack",
          tool: "slash:slack",
          status: "completed",
          outputPreview: issue.summary,
        },
      ],
    }));
  });

  let filtered = synthetic;
  if (componentId) {
    filtered = filtered.filter((item) => item.componentIds.includes(componentId));
  }
  return filtered.slice(0, limit);
}

