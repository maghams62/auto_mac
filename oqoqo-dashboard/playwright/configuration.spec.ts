import { expect, test } from "@playwright/test";

test.describe("Project configuration view", () => {
  test("hides prototype cards when admin flag is disabled", async ({ page }) => {
    await page.goto("/projects/project_atlas/configuration");

    await expect(page.getByText(/Option 1 & 2 prototypes/i)).toBeVisible();
    await expect(page.getByText(/NEXT_PUBLIC_ENABLE_PROTOTYPE_ADMIN=true/i)).toBeVisible();
  });
});

