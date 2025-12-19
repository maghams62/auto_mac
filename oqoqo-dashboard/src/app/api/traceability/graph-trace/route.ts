import { requestCerebrosJson } from "@/lib/clients/cerebros";
import type { ExternalResult } from "@/lib/clients/types";
import { projects as mockProjects } from "@/lib/mock-data";
import { jsonOk } from "@/lib/server/api-response";

type TraceabilityGraphTrace = {
  investigation_id?: string;
  question?: string;
  created_at?: string;
  doc_issue_id?: string;
  doc_issue_title?: string;
  evidence?: Array<{ id?: string; title?: string; source?: string; url?: string }>;
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const componentId = searchParams.get("componentId") ?? undefined;
  const projectId = searchParams.get("projectId") ?? undefined;
  const limit = Math.max(1, Math.min(parseInt(searchParams.get("limit") ?? "3", 10), 10));

  let traces: TraceabilityGraphTrace[] | null = null;
  const dependencies: Record<string, ExternalResult<unknown>> = {};
  let fallbackReason: string | undefined;

  if (componentId) {
    const params = new URLSearchParams({ component_id: componentId, limit: String(limit) });
    const liveResult = await requestCerebrosJson<{ traces?: TraceabilityGraphTrace[] }>(
      `/traceability/graph-trace?${params.toString()}`,
    );
    dependencies.cerebrosGraphTrace = liveResult;
    if (liveResult.status === "OK" && liveResult.data?.traces?.length) {
      traces = liveResult.data.traces;
    } else {
      fallbackReason = "cerebros_unavailable";
    }
  }

  if (!traces || traces.length === 0) {
    traces = fallbackTraces({ componentId, projectId, limit });
    fallbackReason = fallbackReason ?? "synthetic_fallback";
  }

  return jsonOk({
    status: traces.length ? "OK" : "UNAVAILABLE",
    fallbackReason,
    data: traces.length ? { traces } : null,
    dependencies,
    error:
      traces.length > 0
        ? undefined
        : {
            type: "UNKNOWN",
            message: "Traceability data unavailable",
          },
  });
}

function fallbackTraces({
  componentId,
  projectId,
  limit,
}: {
  componentId?: string;
  projectId?: string;
  limit: number;
}): TraceabilityGraphTrace[] {
  const projects = projectId ? mockProjects.filter((project) => project.id === projectId) : mockProjects;
  const traces = projects.flatMap((project) =>
    project.docIssues
      .filter((issue) => !componentId || issue.componentId === componentId)
      .map((issue) => ({
        investigation_id: `${issue.id}-investigation`,
        question: `Why is ${issue.title} drifting?`,
        created_at: issue.detectedAt,
        doc_issue_id: issue.id,
        doc_issue_title: issue.title,
        evidence:
          issue.sourceLinks?.map((link) => ({
            id: link.url,
            title: link.label ?? link.url,
            source: link.type,
            url: link.url,
          })) ?? [],
      }))
  );
  return traces.slice(0, limit);
}

