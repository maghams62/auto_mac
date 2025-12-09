import { expect, test } from "@playwright/test";

test.describe("Dashboard smoke routes", () => {
  test("graph page renders synthetic data", async ({ page }) => {
    await page.goto("/projects/project_atlas/graph?mode=synthetic");
    await expect(page.getByRole("heading", { name: /documentation drift/i })).toBeVisible();
    await expect(page.getByText(/Live Atlas data|Synthetic dataset/)).toBeVisible();
  });

  test("settings page loads the control surface", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Cerebros control surface" })).toBeVisible();
    await expect(page.getByText("Source of truth")).toBeVisible();
  });
});


