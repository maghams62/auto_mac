import { afterEach, describe, expect, it } from "vitest";

import { GET as activityGet } from "@/app/api/activity/route";
import { GET as graphGet } from "@/app/api/graph-snapshot/route";
import { GET as issuesGet } from "@/app/api/issues/route";
import { POST as contextPost } from "@/app/api/context/route";
import { POST as contextFeedbackPost } from "@/app/api/context/feedback/route";

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
};

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
});

const atlasProjectId = "project_atlas";

type ActivityProject = {
  id: string;
  components: Array<{ id: string }>;
};

type ActivityPayload = {
  projects: ActivityProject[];
  snapshot: unknown;
};

type GraphSnapshotNode = {
  id: string;
  type: string;
};

type GraphPayload = {
  snapshot: {
    nodes: GraphSnapshotNode[];
  };
  provider: string;
  fallback?: boolean;
};

type IssuesPayload = {
  issues: Array<{ id: string; componentId: string; dashboardUrl?: string }>;
  provider: string;
  fallback?: boolean;
};

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
  expectGraphFallback?: boolean;
  expectContextFallback?: boolean;
  expectIssueFallback?: boolean;
};

const providerMatrix: ProviderMatrixExpectation[] = [
  { graph: "synthetic", context: "synthetic", issue: "synthetic" },
  { graph: "neo4j", context: "synthetic", issue: "synthetic", expectGraphFallback: true },
  { graph: "synthetic", context: "qdrant", issue: "synthetic", expectContextFallback: true },
  { graph: "synthetic", context: "synthetic", issue: "cerebros", expectIssueFallback: true },
];

describe("API contract smoke tests", () => {
  it("returns live activity snapshot with projects", async () => {
    const response = await activityGet();
    expect(response.status).toBe(200);
    const body = (await response.json()) as ActivityPayload;
    expect(Array.isArray(body.projects)).toBe(true);
    expect(body.projects.length).toBeGreaterThan(0);
    expect(body.snapshot).toBeDefined();
  });

  it("returns graph snapshot for a project", async () => {
    const response = await graphGet(new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}`));
    expect(response.status).toBe(200);
    const body = (await response.json()) as GraphPayload;
    expect(body.snapshot?.nodes?.length).toBeGreaterThan(0);
    expect(body.provider).toBeDefined();
  });

  it("returns issues for a project", async () => {
    const response = await issuesGet(new Request(`http://localhost/api/issues?projectId=${atlasProjectId}`));
    expect(response.status).toBe(200);
    const body = (await response.json()) as IssuesPayload;
    expect(body.issues?.length).toBeGreaterThan(0);
    expect(body.provider).toBeDefined();
  });

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

describe("Provider fallback behavior", () => {
  it("falls back to synthetic graph snapshot when Neo4j is unavailable", async () => {
    process.env.GRAPH_PROVIDER = "neo4j";
    process.env.NEO4J_URI = "";
    process.env.NEO4J_USER = "";
    process.env.NEO4J_PASSWORD = "";
    const response = await graphGet(new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}`));
    expect(response.status).toBe(200);
    const body = (await response.json()) as GraphPayload;
    expect(body.fallback).toBe(true);
    expect(body.snapshot?.nodes?.length).toBeGreaterThan(0);
  });

  it("falls back to synthetic context when Qdrant is unavailable", async () => {
    process.env.CONTEXT_PROVIDER = "qdrant";
    process.env.QDRANT_URL = "";
    process.env.QDRANT_API_KEY = "";
    const response = await contextPost(
      new Request("http://localhost/api/context", {
        method: "POST",
        body: JSON.stringify({ projectId: atlasProjectId }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(response.status).toBe(200);
    const body = (await response.json()) as Awaited<ReturnType<typeof contextPost>> extends Promise<infer R>
      ? R
      : never;
    expect(body.fallback).toBe(true);
    expect(body.snippets.length).toBeGreaterThan(0);
  });

  it("falls back to synthetic issues when Cerebros is unavailable", async () => {
    process.env.ISSUE_PROVIDER = "cerebros";
    process.env.CEREBROS_API_BASE = "";
    const response = await issuesGet(new Request(`http://localhost/api/issues?projectId=${atlasProjectId}`));
    expect(response.status).toBe(200);
    const body = (await response.json()) as ContextPayload;
    expect(body.fallback).toBe(true);
    expect(body.issues.length).toBeGreaterThan(0);
  });
});

describe("Provider matrix combinations", () => {
  providerMatrix.forEach((combo) => {
    const label = `graph=${combo.graph}, context=${combo.context}, issue=${combo.issue}`;
    it(`honors ${label}`, async () => {
      process.env.GRAPH_PROVIDER = combo.graph;
      process.env.CONTEXT_PROVIDER = combo.context;
      process.env.ISSUE_PROVIDER = combo.issue;
      if (combo.expectGraphFallback) {
        process.env.NEO4J_URI = "";
        process.env.NEO4J_USER = "";
        process.env.NEO4J_PASSWORD = "";
      }
      if (combo.expectContextFallback) {
        process.env.QDRANT_URL = "";
        process.env.QDRANT_API_KEY = "";
      }
      if (combo.expectIssueFallback) {
        process.env.CEREBROS_API_BASE = "";
      }

      const graphResponse = await graphGet(new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}`));
      const graphPayload = (await graphResponse.json()) as GraphPayload;
      expect(graphPayload.snapshot.nodes.length).toBeGreaterThan(0);
      expect(Boolean(graphPayload.fallback)).toBe(Boolean(combo.expectGraphFallback));

      const contextResponse = await contextPost(
        new Request("http://localhost/api/context", {
          method: "POST",
          body: JSON.stringify({ projectId: atlasProjectId }),
          headers: { "Content-Type": "application/json" },
        })
      );
      const contextPayload = (await contextResponse.json()) as ContextPayload;
      expect(Boolean(contextPayload.fallback)).toBe(Boolean(combo.expectContextFallback));

      const issuesResponse = await issuesGet(new Request(`http://localhost/api/issues?projectId=${atlasProjectId}`));
      const issuesPayload = (await issuesResponse.json()) as IssuesPayload;
      expect(issuesPayload.issues.length).toBeGreaterThan(0);
      expect(Boolean(issuesPayload.fallback)).toBe(Boolean(combo.expectIssueFallback));
    });
  });
});

describe("Cross-API consistency", () => {
  it("aligns component IDs across activity, graph, and issues", async () => {
    const activityResponse = await activityGet();
    const activityPayload = (await activityResponse.json()) as ActivityPayload;
    const activityProject = activityPayload.projects.find((project) => project.id === atlasProjectId);
    expect(activityProject).toBeDefined();

    const componentIdsFromActivity = new Set(activityProject.components.map((component) => component.id));

    const graphResponse = await graphGet(new Request(`http://localhost/api/graph-snapshot?projectId=${atlasProjectId}`));
    const graphPayload = (await graphResponse.json()) as GraphPayload;
    const graphComponentIds = new Set(
      graphPayload.snapshot.nodes.filter((node) => node.type === "component").map((node) => node.id)
    );

    const issuesResponse = await issuesGet(new Request(`http://localhost/api/issues?projectId=${atlasProjectId}`));
    const issuesPayload = (await issuesResponse.json()) as IssuesPayload;

    issuesPayload.issues.forEach((issue) => {
      expect(componentIdsFromActivity.has(issue.componentId)).toBe(true);
      expect(graphComponentIds.has(issue.componentId)).toBe(true);
      expect(issue.dashboardUrl).toContain(issue.id);
    });
  });
});

