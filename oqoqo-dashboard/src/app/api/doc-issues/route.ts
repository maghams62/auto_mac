import { requestCerebrosJson } from "@/lib/clients/cerebros";
import type { ExternalResult } from "@/lib/clients/types";
import { allowSyntheticFallback, parseLiveMode, resolveServerModeOverride } from "@/lib/mode";
import { projects as mockProjects } from "@/lib/mock-data";
import { jsonOk } from "@/lib/server/api-response";
import { buildDocUrlFromPath } from "@/lib/server/docs";
import type { DocIssue, LiveMode, SourceLink, SourceLinkType } from "@/lib/types";

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

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId");
  const source = searchParams.get("source") ?? "impact-report";
  const limit = Math.max(1, Math.min(parseInt(searchParams.get("limit") ?? "10", 10), 50));

  const forcedMode = parseLiveMode(searchParams.get("mode"));
  const envMode = resolveServerModeOverride();
  const syntheticRequested = forcedMode === "synthetic" || envMode === "synthetic";
  const syntheticFallbackEnabled = syntheticRequested || allowSyntheticFallback();
  let mode: LiveMode = syntheticRequested ? "synthetic" : envMode ?? "atlas";
  let fallbackReason: string | undefined;

  const dependencies: Record<string, ExternalResult<unknown>> = {};

  let issues: DocIssue[] = [];

  if (!syntheticRequested) {
    const cerebrosResult = await fetchImpactDocIssues(projectId, source, limit);
    dependencies.cerebrosImpact = cerebrosResult;
    if (cerebrosResult.status === "OK" && cerebrosResult.data?.length) {
      issues = mapImpactIssues(cerebrosResult.data, projectId ?? "live");
      mode = envMode ?? "atlas";
    } else {
      fallbackReason = "cerebros_unavailable";
    }
  }

  if (issues.length === 0 && syntheticFallbackEnabled) {
    issues = fallbackDocIssues(projectId ?? undefined, limit);
    mode = "synthetic";
    fallbackReason = fallbackReason ?? "synthetic_fallback";
  }

  const prioritizedIssues = prioritizeLiveIssues(issues).slice(0, limit);
  const status = prioritizedIssues.length ? "OK" : "UNAVAILABLE";

  return jsonOk({
    status,
    mode,
    fallbackReason,
    data: prioritizedIssues.length ? { issues: prioritizedIssues } : null,
    dependencies,
    error:
      prioritizedIssues.length > 0
        ? undefined
        : {
            type: "UNKNOWN",
            message: "Doc issues unavailable",
          },
  });
}

function fallbackDocIssues(projectId: string | undefined, limit: number): DocIssue[] {
  const projects = projectId
    ? mockProjects.filter((project) => project.id === projectId)
    : mockProjects;
  const allIssues = projects.flatMap((project) => project.docIssues);
  return allIssues.slice(0, limit).map((issue) => ({
    ...issue,
    docUrl: resolveDocUrl(issue.docUrl, issue.docPath),
  }));
}

function mapImpactDocIssue(issue: ImpactDocIssue, projectId: string): DocIssue {
  const normalizedSeverity = normalizeSeverity(issue.severity ?? issue.impact_level);
  const normalizedStatus = normalizeStatus(issue.state);
  const detectedAt = issue.detected_at ?? issue.created_at ?? new Date().toISOString();
  const updatedAt = issue.updated_at ?? detectedAt;
  const componentId = issue.component_ids?.[0] ?? "component:unknown";
  const repoId = issue.repo_id ?? "repo:unknown";
  const docPath = issue.doc_path ?? issue.doc_title ?? issue.doc_id ?? issue.id ?? "doc";
  const fallbackTitle = issue.doc_title || docPath;

  const normalizedSourceLinks = mapSourceLinks(issue);
  const githubLink = normalizedSourceLinks.find((link) => link.type === "git")?.url ?? issue.change_context?.url;
  const slackLink =
    normalizedSourceLinks.find((link) => link.type === "slack")?.url ??
    issue.change_context?.slack_permalink ??
    issue.slack_context?.permalink;

  return {
    id: issue.id ?? `impact:${repoId}:${docPath}`,
    projectId: issue.project_id ?? projectId,
    componentId,
    repoId,
    docPath,
    title: fallbackTitle,
    summary: issue.summary ?? issue.change_summary ?? issue.change_title ?? "Impact analysis result",
    severity: normalizedSeverity,
    status: normalizedStatus,
    detectedAt,
    updatedAt,
    suggestedFixes: [],
    linkedCode: [],
    divergenceSources: deriveSources(issue),
    originInvestigationId: issue.origin_investigation_id,
    evidenceIds: issue.evidence_ids ?? [],
    signals: {
      gitChurn: 0,
      ticketsMentioned: 0,
      slackMentions: slackLink ? 1 : 0,
      supportMentions: 0,
    },
    docUrl: resolveDocUrl(issue.doc_url, issue.doc_path ?? docPath),
    githubUrl: githubLink,
    slackUrl: slackLink,
    sourceLinks: normalizedSourceLinks,
    brainTraceUrl: issue.brain_trace_url ?? issue.metadata?.brain_trace_url,
    brainUniverseUrl: issue.brain_universe_url ?? issue.metadata?.brain_universe_url,
    queryId: issue.cerebros_query_id ?? issue.metadata?.cerebros_query_id,
  };
}

function normalizeSeverity(severity?: string): DocIssue["severity"] {
  const value = (severity || "").toLowerCase();
  if (value === "critical") return "critical";
  if (value === "high") return "high";
  if (value === "low") return "low";
  return "medium";
}

function normalizeStatus(state?: string): DocIssue["status"] {
  const value = (state || "").toLowerCase();
  if (value === "resolved") return "resolved";
  if (value === "triage") return "triage";
  if (value === "open") return "open";
  return "in_progress";
}

function deriveSources(issue: ImpactDocIssue): DocIssue["divergenceSources"] {
  const sources = new Set<DocIssue["divergenceSources"][number]>();
  const links = issue.links ?? [];
  for (const link of links) {
    if (!link.type) continue;
    if (link.type === "git") sources.add("git");
    if (link.type === "slack") sources.add("slack");
    if (link.type === "doc") sources.add("docs");
  }
  if (sources.size === 0) {
    sources.add("docs");
  }
  return Array.from(sources);
}

function mapSourceLinks(issue: ImpactDocIssue): SourceLink[] {
  const rawLinks = issue.links ?? [];
  return rawLinks
    .map((link, index) => {
      if (!link?.url) return null;
      const type = (link.type as SourceLinkType | undefined) ?? "doc";
      return {
        type,
        url: link.url,
        label: deriveSourceLinkLabel(type, link.url, index),
      };
    })
    .filter((link): link is SourceLink => Boolean(link));
}

function resolveDocUrl(rawUrl?: string | null, fallbackPath?: string | null) {
  if (rawUrl && /^https?:\/\//i.test(rawUrl)) {
    return rawUrl;
  }
  if (rawUrl) {
    return buildDocUrlFromPath(rawUrl);
  }
  return buildDocUrlFromPath(fallbackPath ?? undefined);
}

function deriveSourceLinkLabel(type: SourceLinkType, url: string, index: number) {
  const friendlyType = {
    slack: "Slack",
    git: "Git",
    ticket: "Ticket",
    doc: "Doc",
  }[type];

  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return `${friendlyType} · ${host}`;
  } catch {
    return `${friendlyType} link ${index + 1}`;
  }
}

async function fetchImpactDocIssues(
  projectId: string | null,
  source: string,
  limit: number,
): Promise<ExternalResult<ImpactDocIssue[]>> {
  const params = new URLSearchParams();
  params.set("source", source);
  params.set("limit", Math.min(200, Math.max(limit, 10)).toString());
  if (projectId) {
    params.set("project_id", projectId);
  }
  const result = await requestCerebrosJson<{ doc_issues?: ImpactDocIssue[] }>(`/impact/doc-issues?${params.toString()}`);
  if (result.status !== "OK" || !result.data) {
    return {
      ...result,
      data: null,
    };
  }

  const filtered = (result.data.doc_issues ?? []).filter((issue) => {
    const linked = (issue.linked_change as string | undefined) ?? issue.change_context?.identifier ?? "";
    return !/^slack:slack:/i.test(linked);
  });

  return {
    status: "OK",
    data: filtered,
    meta: {
      provider: "cerebros",
      endpoint: "impact/doc-issues",
    },
  };
}

function mapImpactIssues(upstream: ImpactDocIssue[], fallbackProjectId: string) {
  return upstream.map((issue) => mapImpactDocIssue(issue, issue.project_id ?? fallbackProjectId));
}

function prioritizeLiveIssues(issues: DocIssue[]) {
  const liveRepoIds = new Set(["core-api", "billing-service", "docs-portal"]);
  const docsBase = process.env.NEXT_PUBLIC_DOCS_BASE ?? process.env.DOCS_BASE_URL ?? process.env.DOCS_BASE ?? "";
  const liveGitOrg = process.env.NEXT_PUBLIC_LIVE_GIT_ORG ?? process.env.LIVE_GIT_ORG ?? process.env.GIT_ORG ?? "";

  return issues
    .map((issue) => ({ issue, priority: computePriority(issue, liveRepoIds, docsBase, liveGitOrg) }))
    .sort((a, b) => {
      if (a.priority !== b.priority) {
        return b.priority - a.priority;
      }
      return Date.parse(b.issue.detectedAt) - Date.parse(a.issue.detectedAt);
    })
    .map((entry) => entry.issue);
}

function computePriority(issue: DocIssue, liveRepos: Set<string>, docsBase: string, gitOrg: string) {
  if (liveRepos.has(issue.repoId)) return 3;
  if (docsBase && issue.docUrl?.startsWith(docsBase)) return 2;
  if (gitOrg && issue.githubUrl?.includes(`github.com/${gitOrg}/`)) return 1;
  return 0;
}



