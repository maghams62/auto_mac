import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

const backendOrigin = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";

type GraphSnapshot = {
  nodes: Array<{ id: string; label: string; title?: string }>;
  edges: Array<{ id: string }>;
  meta?: {
    minTimestamp?: string | null;
    maxTimestamp?: string | null;
  };
};

type LayoutStats = {
  layoutCount: number;
  columnCount: number;
  extentX: number;
  extentY: number;
  allowPanZoom: boolean;
  layoutStyle: string;
};

async function setGraphFixture(request: APIRequestContext, mode: "deterministic" | "empty" | "live") {
  let lastBody = "";
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      const response = await request.post(`${backendOrigin}/api/test/graph-fixture`, { data: { mode } });
      if (response.ok()) {
        return;
      }
      lastBody = await response.text();
    } catch (error) {
      lastBody = String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Unable to toggle graph fixture to "${mode}". Last error: ${lastBody}`);
}

const NEO4J_TEST_LIMIT = Number(process.env.NEO4J_TEST_LIMIT || "25");

async function fetchNeo4jSnapshot(
  request: APIRequestContext,
  params?: { modalities?: string[]; snapshotAt?: string | null },
): Promise<GraphSnapshot> {
  const url = new URL("/api/brain/universe", backendOrigin);
  url.searchParams.set("mode", "neo4j_default");
  url.searchParams.set("limit", String(NEO4J_TEST_LIMIT));
  if (params?.modalities?.length) {
    for (const modality of params.modalities) {
      url.searchParams.append("modalities", modality);
    }
  }
  if (params?.snapshotAt) {
    url.searchParams.set("snapshotAt", params.snapshotAt);
  }
  const response = await request.get(url.toString());
  if (!response.ok()) {
    throw new Error(`Failed to fetch snapshot: ${response.status()} ${response.statusText()}`);
  }
  return (await response.json()) as GraphSnapshot;
}

async function gotoNeo4jUniverse(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto("/brain/neo4j/", { waitUntil: "domcontentloaded" });
    const snapshotLocator = page.getByTestId("snapshot-counts-value");
    if (await snapshotLocator.count()) {
      await expect(snapshotLocator).toBeVisible();
      return;
    }
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId("snapshot-counts-value")).toBeVisible();
}

function snapshotMatcher(nodes: number, edges: number) {
  return new RegExp(`Nodes\\s+${nodes}\\s+·\\s+Edges\\s+${edges}`);
}

async function expectSnapshotCounts(page: Page, nodes: number, edges: number) {
  await expect(page.getByTestId("snapshot-counts-value")).toHaveText(snapshotMatcher(nodes, edges));
}

async function waitForLayoutStats(page: Page): Promise<LayoutStats> {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const stats = await page.evaluate<LayoutStats | null>(() => {
      const layout = (window as any).__brainGraphLayout || [];
      const view = (window as any).__brainGraphViewState || {};
      if (!layout.length) {
        return null;
      }
      const xs = layout.map((node: { x: number }) => node.x);
      const ys = layout.map((node: { y: number }) => node.y);
      const maxX = Math.max(...xs);
      const minX = Math.min(...xs);
      const maxY = Math.max(...ys);
      const minY = Math.min(...ys);
      const columnBins = Array.from(
        new Set(layout.map((node: { x: number }) => Math.round(node.x / 25))),
      ).length;
      return {
        layoutCount: layout.length,
        columnCount: columnBins,
        extentX: maxX - minX,
        extentY: maxY - minY,
        allowPanZoom: (view.allowPanZoom ?? true) as boolean,
        layoutStyle: (view.layoutStyle ?? "radial") as string,
      };
    });
    if (stats) {
      return stats;
    }
    await page.waitForTimeout(200);
  }
  throw new Error("Graph layout stats were not available in the browser context.");
}

async function expectHorizontalStaticGraph(page: Page, expectedNodeCount: number) {
  const stats = await waitForLayoutStats(page);
  expect(stats.layoutStyle).toBe("neo4j");
  expect(stats.allowPanZoom).toBe(false);
  expect(stats.layoutCount).toBe(expectedNodeCount);
  expect(stats.columnCount).toBeGreaterThanOrEqual(5);
  expect(stats.extentX).toBeGreaterThan(stats.extentY);
}

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ request }) => {
  await setGraphFixture(request, "live");
});

test("renders Brain Universe snapshot using neo4j_default mode", async ({ page, request }) => {
  const snapshot = await fetchNeo4jSnapshot(request);
  await gotoNeo4jUniverse(page);
  await expectSnapshotCounts(page, snapshot.nodes.length, snapshot.edges.length);
  await expect(page.getByTestId("graph-canvas")).toBeVisible();
  const overview = page.getByTestId("overview-panel");
  await expect(overview).toBeVisible();
  await expect(overview.locator("span").first()).toBeVisible();
  await expectHorizontalStaticGraph(page, snapshot.nodes.length);
});

test("filters down to Slack-only nodes", async ({ page, request }) => {
  const fullSnapshot = await fetchNeo4jSnapshot(request);
  const slackSnapshot = await fetchNeo4jSnapshot(request, { modalities: ["slack"] });

  await gotoNeo4jUniverse(page);
  await expectSnapshotCounts(page, fullSnapshot.nodes.length, fullSnapshot.edges.length);

  const slackChip = page.getByTestId("modality-chip-slack");
  await slackChip.click();
  await expectSnapshotCounts(page, slackSnapshot.nodes.length, slackSnapshot.edges.length);

  await slackChip.click();
  await expectSnapshotCounts(page, fullSnapshot.nodes.length, fullSnapshot.edges.length);
});

test("filters down to Git-only nodes", async ({ page, request }) => {
  const fullSnapshot = await fetchNeo4jSnapshot(request);
  const gitSnapshot = await fetchNeo4jSnapshot(request, { modalities: ["git"] });

  await gotoNeo4jUniverse(page);
  await expectSnapshotCounts(page, fullSnapshot.nodes.length, fullSnapshot.edges.length);
  const gitChip = page.getByTestId("modality-chip-git");
  await gitChip.click();
  await expectSnapshotCounts(page, gitSnapshot.nodes.length, gitSnapshot.edges.length);
});

test.skip("time slider hides later events", async () => {});

test("switching fixture to empty snapshot shows request status", async ({ page, request }) => {
  await gotoNeo4jUniverse(page);
  await setGraphFixture(request, "empty");
  await page.reload();
  await expect(page.getByTestId("graph-request-status")).toContainText("Latest snapshot returned 0 nodes.");
});

test("node hooks drive the detail panel", async ({ page, request }) => {
  const snapshot = await fetchNeo4jSnapshot(request);
  await gotoNeo4jUniverse(page);

  const firstHook = page.locator('[data-testid^="graph-node-hook-"]').first();
  await expect(firstHook).toBeVisible();
  const testId = await firstHook.getAttribute("data-testid");
  if (!testId) {
    throw new Error("Unable to locate node hook test id");
  }
  const nodeId = testId.replace("graph-node-hook-", "");
  const expectedNode = snapshot.nodes.find((node) => node.id === nodeId);

  await firstHook.click();
  if (expectedNode?.title) {
    await expect(page.getByTestId("node-details-panel")).toContainText(expectedNode.title);
  } else {
    await expect(page.getByTestId("node-details-panel")).toBeVisible();
  }
});

