import { expect, test } from "@playwright/test";

test.describe("Project Today overview", () => {
  test("shows hero, top issues, signals, and impact alerts in synthetic mode", async ({ page }) => {
    await page.goto("/projects/project_atlas?mode=synthetic");

    const hero = page.getByTestId("today-hero");
    await expect(hero).toBeVisible();
    await expect(hero.getByTestId("mode-badge")).toHaveText(/synthetic/i);
    await expect(page.getByText(/Option 1 · documentation risk/i)).toBeVisible();

    const topIssues = page.getByTestId("today-top-issues");
    await expect(topIssues.getByRole("button", { name: /view issue/i }).first()).toBeVisible();

    const signals = page.getByTestId("today-signals");
    await expect(signals.getByText(/Latest drift signals/i)).toBeVisible();
    await expect(signals.getByText(/Synthetic demo/i)).toBeVisible();

    const impactAlerts = page.getByTestId("impact-alerts-panel");
    await expect(impactAlerts.getByRole("heading", { name: /docs impact alerts/i })).toBeVisible();
    await expect(page.getByText(/Option 2 · downstream documentation impact/i)).toBeVisible();
  });
});


