import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
  usePathname: () => "/",
  redirect: vi.fn(),
  notFound: vi.fn(),
  useParams: () => ({ projectId: "demo", componentId: "comp_demo", issueId: "issue_demo" }),
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
  revalidateTag: vi.fn(),
}));

const defaultEnvelope = {
  status: "OK",
  data: {},
};

const fetchMock = vi.fn(() =>
  Promise.resolve(
    new Response(JSON.stringify(defaultEnvelope), {
      headers: { "Content-Type": "application/json" },
    }),
  ),
);

beforeAll(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterAll(() => {
  vi.unstubAllGlobals();
});

const moduleLoaders: Array<[string, () => Promise<unknown>]> = [
  ["ActivityGraphPanel", () => import("@/components/activity/activity-graph-panel")],
  ["ImpactAlertsPanel", () => import("@/components/impact/impact-alerts-panel")],
  ["Projects overview page", () => import("@/app/(dashboard)/projects/page")],
  ["Project activity page", () => import("@/app/(dashboard)/projects/[projectId]/activity/page")],
  ["Project impact page", () => import("@/app/(dashboard)/projects/[projectId]/impact/page")],
  ["Project graph page", () => import("@/app/(dashboard)/projects/[projectId]/graph/page")],
  ["Project issues list page", () => import("@/app/(dashboard)/projects/[projectId]/issues/page")],
  ["Project issue detail page", () => import("@/app/(dashboard)/projects/[projectId]/issues/[issueId]/page")],
  ["Project components page", () => import("@/app/(dashboard)/projects/[projectId]/components/page")],
  ["Project component detail page", () => import("@/app/(dashboard)/projects/[projectId]/components/[componentId]/page")],
  ["Project configuration page", () => import("@/app/(dashboard)/projects/[projectId]/configuration/page")],
];

const MODULE_TIMEOUT = 20000;

describe("dashboard module imports", () => {
  it.concurrent.each(moduleLoaders)(
    "%s loads without module errors",
    async (_, loader) => {
      await expect(loader()).resolves.toBeDefined();
    },
    MODULE_TIMEOUT,
  );
});


