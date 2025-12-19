import { expect, test } from "@playwright/test";

async function fetchFirstIncidentId(page: import("@playwright/test").Page): Promise<string | null> {
  const response = await page.request.get("/api/incidents?limit=1");
  if (!response.ok()) {
    return null;
  }
  const payload = await response.json();
  const incident = payload?.data?.incidents?.[0];
  return incident?.id ?? null;
}

test.describe("Incidents overview and detail", () => {
  test("projects dashboard surfaces structured incidents", async ({ page }) => {
    const incidentId = await fetchFirstIncidentId(page);
    test.skip(!incidentId, "No incidents available to inspect");
    await page.goto("/projects");
    const card = page.getByTestId("incident-card").first();
    await expect(card).toBeVisible();
    await expect(card.getByTestId("incident-root-cause")).toBeVisible();
    const chips = card.getByTestId("incident-activity-chip");
    await expect(chips.first()).toBeVisible();
  });

  test("incident detail page shows reasoning panels", async ({ page }) => {
    const incidentId = await fetchFirstIncidentId(page);
    test.skip(!incidentId, "No incidents available to inspect");
    await page.goto(`/incidents/${incidentId}`);
    await expect(page.getByTestId("incident-detail-root-cause")).toBeVisible();
    await expect(page.getByTestId("incident-detail-resolution")).toBeVisible();
    await expect(page.getByTestId("incident-detail-signals")).toBeVisible();
    await expect(page.getByTestId("incident-detail-dependencies")).toBeVisible();
  });
});

