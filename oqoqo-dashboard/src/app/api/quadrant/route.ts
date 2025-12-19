import { requestCerebrosJson } from "@/lib/clients/cerebros";
import type { ExternalResult } from "@/lib/clients/types";
import { projects as mockProjects } from "@/lib/mock-data";
import { resolveServerModeOverride } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import type { QuadrantPoint, LiveMode } from "@/lib/types";

type QuadrantApiResponse = {
  points: QuadrantPoint[];
  timeWindow?: string;
};

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId");
  const limitParam = searchParams.get("limit");
  const windowParam = searchParams.get("window") ?? "7d";
  const limit = Math.min(Math.max(parseInt(limitParam ?? "25", 10) || 25, 1), 100);

  const envMode = resolveServerModeOverride();
  let mode: LiveMode = envMode ?? "synthetic";
  let points: QuadrantPoint[] | null = null;
  let timeWindow: string | undefined;
  let fallbackReason: string | undefined;
  const dependencies: Record<string, ExternalResult<unknown>> = {};

  const liveResult = await fetchQuadrantPoints({ limit, windowParam });
  dependencies.cerebrosQuadrant = liveResult;
  if (liveResult.status === "OK" && liveResult.data?.points?.length) {
    points = liveResult.data.points;
    timeWindow = liveResult.data.timeWindow;
    mode = envMode ?? "atlas";
  } else {
    fallbackReason = "cerebros_unavailable";
  }

  if (!points || !points.length) {
    points = buildFallbackPoints(projectId, limit);
    timeWindow = "synthetic";
    mode = envMode ?? "synthetic";
    fallbackReason = fallbackReason ?? "synthetic_fallback";
  }

  return jsonOk({
    status: points.length ? "OK" : "UNAVAILABLE",
    mode,
    fallbackReason,
    data: points.length
      ? {
          projectId,
          points,
          timeWindow,
          mode,
        }
      : null,
    dependencies,
    error:
      points.length > 0
        ? undefined
        : {
            type: "UNKNOWN",
            message: "Quadrant data unavailable",
          },
  });
}

async function fetchQuadrantPoints({
  limit,
  windowParam,
}: {
  limit: number;
  windowParam: string;
}): Promise<ExternalResult<QuadrantApiResponse>> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  query.set("window", windowParam);
  return requestCerebrosJson<QuadrantApiResponse>(`/activity/quadrant?${query.toString()}`);
}

function buildFallbackPoints(projectId: string | null, limit: number): QuadrantPoint[] {
  const candidateProjects = projectId
    ? mockProjects.filter((project) => project.id === projectId)
    : mockProjects;
  const entries: QuadrantPoint[] = [];

  candidateProjects.forEach((project) => {
    const repoMap = new Map(project.repos.map((repo) => [repo.id, repo]));
    project.components.forEach((component) => {
      const repoId = component.repoIds[0] ?? project.repos[0]?.id ?? "unknown_repo";
      const repoName = repoMap.get(repoId)?.name ?? repoId;
      const gitEvents = component.sourceEvents.filter((event) => event.source === "git").length;
      const slackComplaints = component.sourceEvents.filter(
        (event) => event.source === "slack" && (event.metadata?.sentiment as string | undefined) === "negative"
      ).length;
      const docIssues = component.divergenceInsights.length;
      entries.push({
        componentId: component.id,
        componentName: component.name,
        repoId,
        repoName,
        activityScore: component.graphSignals.activity.score,
        dissatisfactionScore: component.graphSignals.dissatisfaction.score,
        gitEvents,
        slackComplaints,
        docIssues,
      });
    });
  });

  return entries
    .sort((a, b) => b.dissatisfactionScore - a.dissatisfactionScore)
    .slice(0, limit);
}

