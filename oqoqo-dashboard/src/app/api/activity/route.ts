import { NextResponse } from "next/server";

import { fetchLiveActivity } from "@/lib/ingest";
import { mergeLiveActivity } from "@/lib/ingest/mapper";
import { projects as mockProjects } from "@/lib/mock-data";
import { resolveServerModeOverride } from "@/lib/mode";
import { getIngestionConfig } from "@/lib/config";
import { getIssueProvider, syntheticIssueProvider } from "@/lib/issues/providers";
import type { GitEvent, LiveActivitySnapshot, LiveMode, SlackThread } from "@/lib/types";

const CEREBROS_API_BASE =
  process.env.CEREBROS_API_BASE ?? process.env.NEXT_PUBLIC_CEREBROS_API_BASE ?? "";

type ComponentContext = {
  name: string;
  repoName: string;
};

const componentRegistry = mockProjects.reduce<Record<string, ComponentContext>>((acc, project) => {
  project.components.forEach((component) => {
    const repoName =
      component.repoIds
        .map((repoId) => project.repos.find((repo) => repo.id === repoId)?.name)
        .find(Boolean) ?? project.repos[0]?.name ?? component.id;
    acc[component.id] = {
      name: component.name,
      repoName,
    };
  });
  return acc;
}, {});

interface CerebrosTopComponent {
  component_id: string;
  git_events?: number;
  slack_events?: number;
  doc_drift_events?: number;
  doc_count?: number;
  activity_score?: number;
}

interface CerebrosComponentDetail extends CerebrosTopComponent {
  window_days?: number;
  last_event_at?: string | null;
}

async function fetchCerebrosTopComponents(): Promise<CerebrosTopComponent[] | null> {
  if (!CEREBROS_API_BASE) return null;
  try {
    const base = CEREBROS_API_BASE.replace(/\/$/, "");
    const response = await fetch(`${base}/api/activity/top-components?limit=15`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      console.warn("[activity] top-components request failed", response.status);
      return null;
    }
    const payload = (await response.json()) as CerebrosTopComponent[];
    return payload;
  } catch (error) {
    console.warn("[activity] Failed to fetch top components", error);
    return null;
  }
}

async function fetchCerebrosComponentDetail(componentId: string): Promise<CerebrosComponentDetail | null> {
  if (!CEREBROS_API_BASE) return null;
  try {
    const base = CEREBROS_API_BASE.replace(/\/$/, "");
    const response = await fetch(`${base}/api/activity/component/${encodeURIComponent(componentId)}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      console.warn("[activity] component detail failed", componentId, response.status);
      return null;
    }
    return (await response.json()) as CerebrosComponentDetail;
  } catch (error) {
    console.warn("[activity] Failed component detail fetch", componentId, error);
    return null;
  }
}

function createGitEvent(componentId: string, detail: CerebrosComponentDetail): GitEvent | null {
  const context = componentRegistry[componentId];
  if (!context) return null;
  const gitCount = detail.git_events ?? 0;
  if (!gitCount) return null;
  const timestamp = detail.last_event_at ?? new Date().toISOString();
  return {
    repo: context.repoName,
    type: "commit",
    id: `cerebros-git-${componentId}`,
    title: `${gitCount} git events`,
    message: `Cerebros aggregated ${gitCount} git events touching ${context.name}.`,
    url: "",
    author: "cerebros-activity",
    timestamp,
  };
}

function createSlackEvent(componentId: string, detail: CerebrosComponentDetail): SlackThread | null {
  const context = componentRegistry[componentId];
  if (!context) return null;
  const slackTotal = detail.slack_events ?? 0;
  const docDrift = detail.doc_drift_events ?? 0;
  if (!slackTotal && !docDrift) return null;
  const timestamp = detail.last_event_at ?? new Date().toISOString();
  return {
    channel: "cerebros-activity",
    ts: `cerebros-slack-${componentId}`,
    user: "cerebros",
    text: `Cerebros observed ${docDrift} doc drift signals and ${slackTotal} Slack events for ${context.name}.`,
    lastActivityTs: timestamp,
    sentiment: docDrift > 0 ? "negative" : "neutral",
    matchedComponents: [context.name],
  };
}

async function fetchCerebrosActivitySnapshot(): Promise<LiveActivitySnapshot | null> {
  const topComponents = await fetchCerebrosTopComponents();
  if (!topComponents?.length) {
    return null;
  }
  const trackedComponents = topComponents.filter((entry) => componentRegistry[entry.component_id]);
  if (!trackedComponents.length) {
    return null;
  }

  const detailEntries = await Promise.all(
    trackedComponents.map(async (entry) => {
      const detail =
        (await fetchCerebrosComponentDetail(entry.component_id)) ??
        null;
      return detail ? detail : null;
    })
  );
  const gitEvents: GitEvent[] = [];
  const slackThreads: SlackThread[] = [];

  detailEntries.forEach((detail) => {
    if (!detail) return;
    const componentId = detail.component_id;
    if (!componentRegistry[componentId]) return;
    const gitEvent = createGitEvent(componentId, detail);
    if (gitEvent) {
      gitEvents.push(gitEvent);
    }
    const slackEvent = createSlackEvent(componentId, detail);
    if (slackEvent) {
      slackThreads.push(slackEvent);
    }
  });

  if (!gitEvents.length && !slackThreads.length) {
    return null;
  }

  return {
    git: gitEvents,
    slack: slackThreads,
    generatedAt: new Date().toISOString(),
  };
}

export async function GET() {
  const componentNames = mockProjects.flatMap((project) => project.components.map((component) => component.name));

  const envMode = resolveServerModeOverride();
  let mode: LiveMode = envMode ?? "synthetic";
  const issueProvider = getIssueProvider();

  let snapshot = await fetchCerebrosActivitySnapshot();
  if (snapshot) {
    mode = envMode ?? "atlas";
  } else {
    const hasConfig = Boolean(getIngestionConfig());
    snapshot = await fetchLiveActivity(componentNames);
    if (snapshot) {
      mode = envMode ?? (hasConfig ? "atlas" : "synthetic");
    }
  }

  if (!snapshot) {
    return NextResponse.json({ error: "Live activity not configured" }, { status: 503 });
  }

  const mergedProjects = mergeLiveActivity(mockProjects, snapshot).map((project) => ({
    ...project,
    mode,
  }));

  const issueResults = await Promise.all(
    mergedProjects.map(async (project) => {
      try {
        return await issueProvider.fetchIssues(project.id);
      } catch (error) {
        console.warn("[activity] issue provider failed", project.id, error);
        if (issueProvider.name !== "synthetic") {
          try {
            return await syntheticIssueProvider.fetchIssues(project.id);
          } catch (fallbackError) {
            console.warn("[activity] synthetic issue provider failed", project.id, fallbackError);
          }
        }
        return null;
      }
    })
  );

  const projectsWithIssues = mergedProjects.map((project) => {
    const issues = issueResults.find((result) => result?.projectId === project.id);
    return issues ? { ...project, docIssues: issues.issues } : project;
  });

  return NextResponse.json(
    {
      snapshot,
      projects: projectsWithIssues,
      mode,
    },
    { status: 200 }
  );
}

