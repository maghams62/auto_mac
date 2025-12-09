import { requestCerebrosJson } from "@/lib/clients/cerebros";
import type { ExternalResult } from "@/lib/clients/types";
import { projects as mockProjects } from "@/lib/mock-data";
import { parseLiveMode, resolveServerModeOverride } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import type { DocIssue, LiveMode } from "@/lib/types";

const MAX_LIMIT = 50;

type ImpactDocIssue = {
  id?: string;
  doc_id?: string;
  doc_title?: string;
  doc_path?: string;
  doc_url?: string;
  repo_id?: string;
  component_ids?: string[];
  impact_level?: string;
  severity?: string;
  state?: string;
  summary?: string;
  change_summary?: string;
  change_title?: string;
  change_context?: {
    url?: string;
    slack_permalink?: string;
  };
  slack_context?: {
    permalink?: string;
  };
  links?: Array<{ type?: string; url?: string }>;
  detected_at?: string;
  updated_at?: string;
  created_at?: string;
  project_id?: string;
  origin_investigation_id?: string;
  evidence_ids?: string[];
};

type ImpactDocIssuesResponse = {
  doc_issues?: ImpactDocIssue[];
  mode?: LiveMode | string;
  fallback?: boolean;
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const searchParams = new URLSearchParams(url.search);
  const limit = clampLimit(searchParams.get("limit"));

  const requestedMode = parseLiveMode(searchParams.get("mode"));
  if (requestedMode) {
    searchParams.delete("mode");
  }

  const envMode = resolveServerModeOverride();
  const syntheticOnly = requestedMode === "synthetic" || envMode === "synthetic";

  let resolvedMode: LiveMode = syntheticOnly ? "synthetic" : envMode ?? "atlas";
  let fallback = syntheticOnly;
  let docIssues: ImpactDocIssue[] = [];
  let fallbackReason: string | undefined;

  const dependencies: Record<string, ExternalResult<unknown>> = {};

  if (!syntheticOnly) {
    const authHeader = request.headers.get("authorization");
    const liveResult = await requestCerebrosJson<ImpactDocIssuesResponse>(`/impact/doc-issues?${searchParams.toString()}`, {
      headers: authHeader ? { Authorization: authHeader } : undefined,
    });
    dependencies.cerebrosImpact = liveResult;
    if (liveResult.status === "OK" && liveResult.data?.doc_issues?.length) {
      docIssues = liveResult.data.doc_issues;
      const upstreamMode = liveResult.data.mode ? parseLiveMode(String(liveResult.data.mode)) : null;
      if (upstreamMode) {
        resolvedMode = upstreamMode;
      } else {
        resolvedMode = envMode ?? "atlas";
      }
      fallback = Boolean(liveResult.data.fallback);
    } else {
      fallbackReason = "cerebros_unavailable";
    }
  }

  if (!docIssues.length) {
    docIssues = buildSyntheticDocIssues(searchParams);
    fallback = true;
    resolvedMode = "synthetic";
    fallbackReason = fallbackReason ?? "synthetic_fallback";
  }

  const trimmed = docIssues.slice(0, limit);
  const status = trimmed.length ? "OK" : "UNAVAILABLE";

  return jsonOk({
    status,
    mode: resolvedMode,
    fallbackReason,
    data: trimmed.length
      ? {
          doc_issues: trimmed,
          mode: resolvedMode,
          fallback,
        }
      : null,
    dependencies,
    error:
      trimmed.length > 0
        ? undefined
        : {
            type: "UNKNOWN",
            message: "Impact doc issues unavailable",
          },
  });
}

function clampLimit(rawLimit: string | null): number {
  const parsed = Number.parseInt(rawLimit ?? "", 10);
  if (Number.isNaN(parsed)) {
    return 25;
  }
  return Math.max(1, Math.min(parsed, MAX_LIMIT));
}

function buildSyntheticDocIssues(searchParams: URLSearchParams): ImpactDocIssue[] {
  const projectFilter = searchParams.get("project_id") ?? searchParams.get("projectId") ?? undefined;
  const componentFilter = searchParams.get("component_id") ?? undefined;
  const serviceFilter = searchParams.get("service_id") ?? undefined;
  const impactFilter = (searchParams.get("impact_level") ?? "").toLowerCase();

  const projects = projectFilter
    ? mockProjects.filter((project) => project.id === projectFilter)
    : mockProjects;

  const issues = projects.flatMap((project) =>
    project.docIssues.map((issue) => mapDashboardIssueToImpact(issue)),
  );

  return issues.filter((issue) => {
    if (componentFilter && !issue.component_ids?.includes(componentFilter)) {
      return false;
    }
    if (serviceFilter && issue.repo_id !== serviceFilter) {
      return false;
    }
    if (impactFilter && (issue.impact_level ?? "").toLowerCase() !== impactFilter) {
      return false;
    }
    return true;
  });
}

function mapDashboardIssueToImpact(issue: DocIssue): ImpactDocIssue {
  const links: ImpactDocIssue["links"] = [];
  if (issue.githubUrl) {
    links.push({ type: "git", url: issue.githubUrl });
  }
  if (issue.slackUrl) {
    links.push({ type: "slack", url: issue.slackUrl });
  }
  if (issue.docUrl) {
    links.push({ type: "doc", url: issue.docUrl });
  }

  return {
    id: issue.id,
    doc_id: issue.id,
    doc_title: issue.title,
    doc_path: issue.docPath,
    doc_url: issue.docUrl,
    repo_id: issue.repoId,
    component_ids: [issue.componentId],
    impact_level: issue.severity,
    severity: issue.severity,
    state: issue.status,
    summary: issue.summary,
    change_summary: issue.summary,
    change_context: issue.githubUrl ? { url: issue.githubUrl } : undefined,
    slack_context: issue.slackUrl ? { permalink: issue.slackUrl } : undefined,
    links,
    detected_at: issue.detectedAt,
    updated_at: issue.updatedAt,
    created_at: issue.detectedAt,
    project_id: issue.projectId,
    origin_investigation_id: issue.originInvestigationId,
    evidence_ids: issue.evidenceIds,
  };
}


