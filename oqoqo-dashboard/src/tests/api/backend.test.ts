import { afterEach, describe, expect, it, vi } from "vitest";

import { GET as activityGet } from "@/app/api/activity/route";
import { GET as graphGet } from "@/app/api/graph-snapshot/route";
import { GET as metricsGet } from "@/app/api/graph-metrics/route";
import { GET as issuesGet } from "@/app/api/issues/route";
import { POST as contextPost } from "@/app/api/context/route";
import { POST as contextFeedbackPost } from "@/app/api/context/feedback/route";
import { GET as investigationsGet } from "@/app/api/investigations/route";
import type { GraphMetrics, LiveGraphSnapshot } from "@/lib/graph/live-types";
import * as ingest from "@/lib/ingest";

const ORIGINAL_ENV = {
  GRAPH_PROVIDER: process.env.GRAPH_PROVIDER,
  CONTEXT_PROVIDER: process.env.CONTEXT_PROVIDER,
  ISSUE_PROVIDER: process.env.ISSUE_PROVIDER,
  NEO4J_URI: process.env.NEO4J_URI,
  NEO4J_USER: process.env.NEO4J_USER,
  NEO4J_PASSWORD: process.env.NEO4J_PASSWORD,
  QDRANT_URL: process.env.QDRANT_URL,
  QDRANT_API_KEY: process.env.QDRANT_API_KEY,
  CEREBROS_API_BASE: process.env.CEREBROS_API_BASE,
  ALLOW_SYNTHETIC_FALLBACK: process.env.ALLOW_SYNTHETIC_FALLBACK,
  OQOQO_MODE: process.env.OQOQO_MODE,
};

const originalFetch = global.fetch;

afterEach(() => {
  process.env.GRAPH_PROVIDER = ORIGINAL_ENV.GRAPH_PROVIDER;
  process.env.CONTEXT_PROVIDER = ORIGINAL_ENV.CONTEXT_PROVIDER;
  process.env.ISSUE_PROVIDER = ORIGINAL_ENV.ISSUE_PROVIDER;
  process.env.NEO4J_URI = ORIGINAL_ENV.NEO4J_URI;
  process.env.NEO4J_USER = ORIGINAL_ENV.NEO4J_USER;
  process.env.NEO4J_PASSWORD = ORIGINAL_ENV.NEO4J_PASSWORD;
  process.env.QDRANT_URL = ORIGINAL_ENV.QDRANT_URL;
  process.env.QDRANT_API_KEY = ORIGINAL_ENV.QDRANT_API_KEY;
  process.env.CEREBROS_API_BASE = ORIGINAL_ENV.CEREBROS_API_BASE;
  process.env.ALLOW_SYNTHETIC_FALLBACK = ORIGINAL_ENV.ALLOW_SYNTHETIC_FALLBACK;
  process.env.OQOQO_MODE = ORIGINAL_ENV.OQOQO_MODE;
  global.fetch = originalFetch;
});

const atlasProjectId = "project_atlas";

type ActivityProject = {
  id: string;
  components: Array<{ id: string }>;
};

type ApiEnvelope<T> = {
  status: string;
  data: T | null;
  mode?: string;
  fallbackReason?: string;
  error?: { message: string };
  dependencies?: Record<string, { status: string }>;
};

type ActivityPayload = ApiEnvelope<{
  projects: ActivityProject[];
  snapshot: unknown;
}>;

type GraphPayload = ApiEnvelope<{
  snapshot: LiveGraphSnapshot;
  provider: string;
  fallback?: boolean;
  fallbackProvider?: string;
}>;

type GraphMetricsPayload = ApiEnvelope<{
  provider: string;
  metrics: GraphMetrics;
  fallback?: boolean;
}>;

type IssuesPayload = ApiEnvelope<{
  issues: Array<{ id: string; componentId: string; dashboardUrl?: string }>;
  provider: string;
  fallback?: boolean;
}>;

type ContextPayload = {
  projectId: string;
  snippets: Array<{ id?: string }>;
  provider?: string;
  fallback?: boolean;
};

type ContextFeedbackPayload = {
  ok: boolean;
};

type ProviderMatrixExpectation = {
  graph: "synthetic" | "neo4j";
  context: "synthetic" | "qdrant";
  issue: "synthetic" | "cerebros";
};

const providerMatrix: ProviderMatrixExpectation[] = [
  { graph: "synthetic", context: "synthetic", issue: "synthetic" },
];

describe("API contract smoke tests", () => {
  it("returns live activity snapshot with projects", async () => {
    const response = await activityGet(new Request("http://localhost/api/activity?mode=synthetic"));
    expect(response.status).toBe(200);
    const body = (await response.json()) as ActivityPayload;
    expect(body.status).toBe("OK");
    expect(Array.isArray(body.data?.projects)).toBe(true);
    expect(body.data?.projects.length).toBeGreaterThan(0);
    expect(body.data?.snapshot).toBeDefined();
  });

  it("returns graph snapshot for a project", async () => {
    const response = await graphGet(new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}`));
    expect(response.status).toBe(200);
    const body = (await response.json()) as GraphPayload;
    expect(body.data?.snapshot?.components?.length).toBeGreaterThan(0);
    expect(body.data?.provider).toBeDefined();
  });

  it("returns graph metrics with KPIs", async () => {
    const response = await metricsGet(new Request("http://localhost/api/graph-metrics"));
    expect(response.status).toBe(200);
    const body = (await response.json()) as GraphMetricsPayload;
    expect(Array.isArray(body.data?.metrics.kpis)).toBe(true);
    expect(body.data?.metrics.kpis.length).toBeGreaterThan(0);
  });

  it("returns issues for a project", async () => {
    const response = await issuesGet(
      new Request(`http://localhost/api/issues?projectId=${atlasProjectId}&mode=synthetic`)
    );
    expect(response.status).toBe(200);
    const body = (await response.json()) as IssuesPayload;
    expect(body.data?.issues?.length).toBeGreaterThan(0);
    expect(body.data?.provider).toBeDefined();
  }, 10_000);

  it("returns context snippets", async () => {
    const response = await contextPost(
      new Request("http://localhost/api/context", {
        method: "POST",
        body: JSON.stringify({ projectId: atlasProjectId }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(response.status).toBe(200);
    const body = (await response.json()) as ContextPayload;
    expect(Array.isArray(body.snippets)).toBe(true);
    expect(body.projectId).toBe(atlasProjectId);
  });

  it("accepts context feedback", async () => {
    const response = await contextFeedbackPost(
      new Request("http://localhost/api/context/feedback", {
        method: "POST",
        body: JSON.stringify({ snippetId: "test-snippet", dismissed: true }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(response.status).toBe(200);
    const body = (await response.json()) as ContextFeedbackPayload;
    expect(body.ok).toBe(true);
  });
});

describe("Live-mode safeguards", () => {
  it("surface dependency failures from git and slack ingest", async () => {
    process.env.CEREBROS_API_BASE = "";
    process.env.OQOQO_MODE = "atlas";
    const ingestSpy = vi.spyOn(ingest, "fetchLiveActivity").mockResolvedValue({
      status: "UNAVAILABLE",
      data: {
        git: [],
        slack: [],
        generatedAt: new Date().toISOString(),
      },
      meta: { provider: "ingest", endpoint: "live-activity" },
      error: { type: "NETWORK", message: "ingest unavailable" },
      dependencies: {
        git: { status: "UNAVAILABLE", data: null, error: { type: "PERMISSION", message: "Token rejected" }, meta: { provider: "github" } },
        slack: { status: "UNAVAILABLE", data: null, error: { type: "RATE_LIMIT", message: "Slack rate limit" }, meta: { provider: "slack" } },
      },
    });

    const response = await activityGet(new Request("http://localhost/api/activity"));
    const body = (await response.json()) as ActivityPayload;
    expect(body.status).toBe("UNAVAILABLE");
    ingestSpy.mockRestore();
  });

  it("propagates upstream non-JSON errors from the issues route", async () => {
    process.env.CEREBROS_API_BASE = "http://live.test";
    process.env.ALLOW_SYNTHETIC_FALLBACK = "0";
    global.fetch = vi.fn().mockResolvedValue(
      new Response("<!DOCTYPE html><html><body>502</body></html>", {
        status: 502,
        headers: { "content-type": "text/html" },
      })
    );

    const response = await issuesGet(new Request(`http://localhost/api/issues?projectId=${atlasProjectId}`));
    expect(response.status).toBe(200);
    const body = (await response.json()) as IssuesPayload;
    expect(body.status).toBe("UNAVAILABLE");
    expect(body.error?.message).toMatch(/Cerebros request failed/i);
  });

  it("returns a 502 when live activity is unavailable and fallback is disabled", async () => {
    process.env.CEREBROS_API_BASE = "http://live.test";
    process.env.ALLOW_SYNTHETIC_FALLBACK = "0";
    global.fetch = vi.fn().mockResolvedValue(
      new Response("bad gateway", {
        status: 502,
        headers: { "content-type": "text/plain" },
      })
    );

    const response = await activityGet(new Request("http://localhost/api/activity"));
    expect(response.status).toBe(200);
    const body = (await response.json()) as ActivityPayload;
    expect(body.status).toBe("UNAVAILABLE");
    expect(body.error?.message).toMatch(/Live activity unavailable/i);
  });

  it("falls back to synthetic investigations when Cerebros is down", async () => {
    process.env.CEREBROS_API_BASE = "http://live.test";
    global.fetch = vi.fn().mockResolvedValue(
      new Response("upstream failure", {
        status: 500,
        headers: { "content-type": "text/plain" },
      })
    );

    const response = await investigationsGet(
      new Request(`http://localhost/api/investigations?projectId=${atlasProjectId}&mode=atlas`)
    );
    expect(response.status).toBe(200);
    const body = (await response.json()) as ApiEnvelope<{ investigations: Array<{ id: string }> }>;
    expect(body.mode).toBe("synthetic");
    expect(body.data?.investigations.length).toBeGreaterThan(0);
  });
});

describe("Provider matrix combinations", () => {
  providerMatrix.forEach((combo) => {
    const label = `graph=${combo.graph}, context=${combo.context}, issue=${combo.issue}`;
    it(`honors ${label}`, async () => {
      process.env.GRAPH_PROVIDER = combo.graph;
      process.env.CONTEXT_PROVIDER = combo.context;
      process.env.ISSUE_PROVIDER = combo.issue;
      const graphResponse = await graphGet(new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}`));
      const graphPayload = (await graphResponse.json()) as GraphPayload;
      expect(graphPayload.data?.snapshot.components.length).toBeGreaterThan(0);
      expect(Boolean(graphPayload.data?.fallback)).toBe(false);

      const contextResponse = await contextPost(
        new Request("http://localhost/api/context", {
          method: "POST",
          body: JSON.stringify({ projectId: atlasProjectId }),
          headers: { "Content-Type": "application/json" },
        })
      );
      const contextPayload = (await contextResponse.json()) as ContextPayload;
      expect(Boolean(contextPayload.fallback)).toBe(false);

      const issuesResponse = await issuesGet(new Request(`http://localhost/api/issues?projectId=${atlasProjectId}`));
      const issuesPayload = (await issuesResponse.json()) as IssuesPayload;
      expect(issuesPayload.data?.issues.length).toBeGreaterThan(0);
      expect(Boolean(issuesPayload.data?.fallback)).toBe(false);
    });
  });
});

describe("Mode overrides", () => {
  it("forces synthetic activity mode when requested", async () => {
    const response = await activityGet(new Request("http://localhost/api/activity?mode=synthetic"));
    expect(response.status).toBe(200);
    const body = (await response.json()) as ActivityPayload;
    expect(body.mode).toBe("synthetic");
    expect(body.data?.projects.length).toBeGreaterThan(0);
  });

  it("forces synthetic providers for graph and issues when requested", async () => {
    const graphResponse = await graphGet(
      new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}&mode=synthetic`)
    );
    const graphPayload = (await graphResponse.json()) as GraphPayload;
    expect(graphPayload.data?.provider).toBe("synthetic");
    expect(graphPayload.data?.fallback).toBe(false);

    const metricsResponse = await metricsGet(new Request("http://localhost/api/graph-metrics?mode=synthetic"));
    const metricsPayload = (await metricsResponse.json()) as GraphMetricsPayload;
    expect(metricsPayload.data?.provider).toBe("synthetic");
    expect(metricsPayload.data?.fallback).toBe(false);

    const issuesResponse = await issuesGet(
      new Request(`http://localhost/api/issues?projectId=${atlasProjectId}&mode=synthetic`)
    );
    const issuesPayload = (await issuesResponse.json()) as IssuesPayload;
    expect(issuesPayload.data?.provider).toBe("synthetic");
    expect(issuesPayload.data?.fallback).toBe(false);

    const contextResponse = await contextPost(
      new Request("http://localhost/api/context?mode=synthetic", {
        method: "POST",
        body: JSON.stringify({ projectId: atlasProjectId }),
        headers: { "Content-Type": "application/json" },
      })
    );
    const contextPayload = (await contextResponse.json()) as ContextPayload;
    expect(contextPayload.provider).toBe("synthetic");
    expect(contextPayload.fallback).toBe(false);
  });
});

describe("Cross-API consistency", () => {
  it("aligns component IDs across activity, graph, and issues", async () => {
    const activityResponse = await activityGet(new Request("http://localhost/api/activity?mode=synthetic"));
    const activityPayload = (await activityResponse.json()) as ActivityPayload;
    const activityProject = activityPayload.data?.projects.find((project) => project.id === atlasProjectId);
    expect(activityProject).toBeDefined();

    const componentIdsFromActivity = new Set(
      (activityProject?.components ?? []).map((component) => component.id)
    );

    const graphResponse = await graphGet(
      new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}&mode=synthetic`)
    );
    const graphPayload = (await graphResponse.json()) as GraphPayload;
    const graphComponentIds = new Set(
      (graphPayload.data?.snapshot.components ?? []).map((component) => component.id),
    );

    const issuesResponse = await issuesGet(
      new Request(`http://localhost/api/issues?projectId=${atlasProjectId}&mode=synthetic`)
    );
    const issuesPayload = (await issuesResponse.json()) as IssuesPayload;

    issuesPayload.data?.issues.forEach((issue) => {
      expect(componentIdsFromActivity.has(issue.componentId)).toBe(true);
      expect(graphComponentIds.has(issue.componentId)).toBe(true);
      expect(issue.dashboardUrl).toContain(issue.id);
    });
  });
});

