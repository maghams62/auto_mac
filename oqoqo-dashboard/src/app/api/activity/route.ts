import type { LiveGraphComponent, LiveGraphSnapshot } from "@/lib/graph/live-types";
import { fetchLiveActivity } from "@/lib/ingest";
import { fetchSyntheticSnapshot } from "@/lib/ingest/synthetic";
import { getIssueProvider } from "@/lib/issues/providers";
import type { IssueProvider } from "@/lib/issues/providers/types";
import { requestCerebrosJson } from "@/lib/clients/cerebros";
import type { ExternalResult } from "@/lib/clients/types";
import { fetchNeo4jSnapshot } from "@/lib/clients/neo4j";
import { mergeLiveActivity } from "@/lib/ingest/mapper";
import { projects as mockProjects } from "@/lib/mock-data";
import { allowSyntheticFallback, isLiveLike, parseLiveMode, resolveServerModeOverride } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import { logDependencyFailure } from "@/lib/server/dependency-log";
import type {
  ComponentNode,
  DocIssue,
  LiveActivitySnapshot,
  LiveMode,
  Project,
  SignalBundle,
} from "@/lib/types";

function buildSignalBundleFromScore(score: number, summary: string): SignalBundle {
  return {
    score: Math.max(0, Math.min(100, Number.isFinite(score) ? score : 0)),
    trend: "flat",
    window: "7d",
    summary,
    metrics: [],
  };
}

function mapLiveComponentToNode(component: LiveGraphComponent, project: Project): ComponentNode {
  const fallbackRepo = component.repoId ?? project.repos[0]?.id ?? "live_repo";
  return {
    id: component.id,
    projectId: project.id,
    name: component.name ?? component.id,
    serviceType: component.tags?.[0] ?? "Service",
    ownerTeam: "Live ingest",
    repoIds: [fallbackRepo],
    docSections: [],
    tags: component.tags ?? [],
    defaultDocUrl: undefined,
    graphSignals: {
      activity: buildSignalBundleFromScore(component.activityScore ?? 0, "Live activity score"),
      drift: buildSignalBundleFromScore(component.driftScore ?? 0, "Live drift score"),
      dissatisfaction: buildSignalBundleFromScore(component.supportPressure ?? 0, "Live support pressure"),
      timeline: [],
    },
    sourceEvents: [],
    divergenceInsights: [],
  };
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const forcedMode = parseLiveMode(searchParams.get("mode"));
  const templateComponentNames = mockProjects.flatMap((project) => project.components.map((component) => component.name));
  const envMode = resolveServerModeOverride();
  const syntheticRequested = forcedMode === "synthetic" || envMode === "synthetic";
  const syntheticFallbackEnabled = syntheticRequested || allowSyntheticFallback();
  let mode: LiveMode = syntheticRequested ? "synthetic" : envMode ?? "atlas";

  const dependencies: Record<string, ExternalResult<unknown>> = {};
  let fallbackReason: string | undefined;

  let snapshotResult: ExternalResult<LiveActivitySnapshot> | null = null;

  if (syntheticRequested) {
    snapshotResult = await wrapSyntheticSnapshot(templateComponentNames);
  } else {
    const cerebrosSnapshot = await fetchCerebrosActivitySnapshot();
    dependencies.cerebrosActivity = cerebrosSnapshot;
    if (cerebrosSnapshot.status === "OK" && cerebrosSnapshot.data) {
      snapshotResult = cerebrosSnapshot;
      mode = envMode ?? "atlas";
    } else {
      fallbackReason = "cerebros_unavailable";
      const liveActivity = await fetchLiveActivity(templateComponentNames);
      dependencies.git = liveActivity.dependencies.git;
      dependencies.slack = liveActivity.dependencies.slack;
      snapshotResult = liveActivity;
    }
  }

  if ((!snapshotResult || !snapshotResult.data) && syntheticFallbackEnabled) {
    snapshotResult = await wrapSyntheticSnapshot(templateComponentNames);
    mode = "synthetic";
    fallbackReason = fallbackReason ?? "synthetic_fallback";
  }

  if (!snapshotResult?.data) {
    return jsonOk({
      status: "UNAVAILABLE",
      data: null,
      mode: "error",
      fallbackReason,
      dependencies,
      error: snapshotResult?.error ?? {
        type: "UNKNOWN",
        message: "Live activity unavailable",
      },
    });
  }

  const { projects: baseProjects, dependency: graphDependency } = await hydrateProjectsForMode(mockProjects, mode);
  if (graphDependency) {
    dependencies.graphSnapshots = graphDependency;
  }

  const mergedProjects = mergeLiveActivity(baseProjects, snapshotResult.data).map((project) => ({
    ...project,
    mode,
  }));

  const issueProvider = getIssueProvider(mode === "synthetic" ? "synthetic" : null);
  const issues = await fetchIssuesForProjects(issueProvider, mergedProjects);
  dependencies.docIssues = issues.aggregate;

  const projectsWithIssues = mergedProjects.map((project) => {
    const issueResult = issues.byProject[project.id];
    if (issueResult?.status === "OK" && issueResult.data) {
      return { ...project, docIssues: issueResult.data };
    }
    return project;
  });

  return jsonOk({
    status: snapshotResult.status,
    mode,
    fallbackReason,
    data: {
      snapshot: snapshotResult.data,
      projects: projectsWithIssues,
    },
    dependencies,
  });
}

async function wrapSyntheticSnapshot(componentNames: string[]): Promise<ExternalResult<LiveActivitySnapshot>> {
  const snapshot = await fetchSyntheticSnapshot(componentNames);
  return {
    status: "OK",
    data: snapshot,
    meta: {
      provider: "synthetic",
      endpoint: "activity/snapshot",
    },
  };
}

async function fetchCerebrosActivitySnapshot(): Promise<ExternalResult<LiveActivitySnapshot>> {
  const result = await requestCerebrosJson<LiveActivitySnapshot>("/activity/snapshot?limit=20");
  return result;
}

async function hydrateProjectsForMode(projects: Project[], mode: LiveMode) {
  if (!isLiveLike(mode)) {
    return { projects, dependency: null };
  }

  const perProject: Record<string, ExternalResult<LiveGraphSnapshot>> = {};
  const hydrated = await Promise.all(
    projects.map(async (project) => {
      const snapshot = await fetchNeo4jSnapshot(project.id);
      perProject[project.id] = snapshot;
      if (snapshot.status !== "OK" || !snapshot.data?.components?.length) {
        return project;
      }
      const liveComponents = snapshot.data.components.map((component) => mapLiveComponentToNode(component, project));
      return {
        ...project,
        components: liveComponents,
        docIssues: [],
      };
    }),
  );

  return {
    projects: hydrated,
    dependency: summarizeDependencyRecords("graph", "snapshot", perProject),
  };
}

async function fetchIssuesForProjects(provider: IssueProvider, projects: Project[]) {
  const result: Record<string, ExternalResult<DocIssue[]>> = {};
  await Promise.all(
    projects.map(async (project) => {
      try {
        const payload = await provider.fetchIssues(project.id);
        result[project.id] = {
          status: "OK",
          data: payload.issues,
          meta: {
            provider: provider.name,
            endpoint: `doc-issues:${project.id}`,
          },
        };
      } catch (error) {
        const errorInfo = {
          type: "UNKNOWN",
          message: error instanceof Error ? error.message : "Doc issues upstream error",
        };
        logDependencyFailure({ provider: provider.name, endpoint: `doc-issues:${project.id}` }, errorInfo);
        result[project.id] = {
          status: "UNAVAILABLE",
          data: null,
          error: errorInfo,
          meta: {
            provider: provider.name,
            endpoint: `doc-issues:${project.id}`,
          },
        };
      }
    }),
  );

  return {
    byProject: result,
    aggregate: summarizeDependencyRecords("issues", "doc-issues", result),
  };
}

function summarizeDependencyRecords<T>(
  provider: string,
  endpoint: string,
  records: Record<string, ExternalResult<T>>,
): ExternalResult<Record<string, ExternalResult<T>>> {
  const values = Object.values(records);
  if (values.length === 0) {
    return {
      status: "NOT_FOUND",
      data: {},
      error: {
        type: "UNKNOWN",
        message: "No dependency records",
      },
      meta: { provider, endpoint },
    };
  }
  const allOk = values.every((entry) => entry.status === "OK");
  return {
    status: allOk ? "OK" : "UNAVAILABLE",
    data: records,
    error: allOk
      ? undefined
      : {
          type: "UNKNOWN",
          message: "Partial dependency failure",
        },
    meta: { provider, endpoint },
  };
}

