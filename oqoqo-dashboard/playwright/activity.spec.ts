import { expect, test } from "@playwright/test";

test.describe("Activity drift view", () => {
  test("system map, doc issues, and timeline slider surface real data", async ({ page }) => {
    await page.goto("/projects/project_atlas/activity?mode=synthetic");

    await expect(page.getByRole("heading", { name: /documentation drift/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /System map/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Doc issues to fix/i })).toBeVisible();

    const slider = page.getByTestId("timeline-slider");
    const firstIssueCard = page.getByTestId("doc-issue-card").first();
    await expect(firstIssueCard).toBeVisible();
    const firstHttpLink = firstIssueCard.locator("a[href^='http']");
    await expect(firstHttpLink.first()).toHaveAttribute("href", /https?:\/\//);

    const initialSummary = await page.getByTestId("timeline-summary").innerText();
    await slider.evaluate((input: HTMLInputElement) => {
      input.value = input.min;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await expect(page.getByTestId("timeline-summary")).not.toHaveText(initialSummary);
  });
});


