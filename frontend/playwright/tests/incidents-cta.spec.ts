import { expect, test } from "@playwright/test";

test.describe("Cerebros incident CTA", () => {
  test("slash cerebros response can be promoted to incident", async ({ page }) => {
    await page.goto("/desktop");
    const input = page.getByTestId("chat-input");
    await expect(input).toBeEnabled({ timeout: 60_000 });
    await input.fill("/cerebros What is happening with the billing support spike?");
    await input.press("Enter");

    const cta = page.getByRole("button", { name: /create incident/i });
    await expect(cta).toBeVisible({ timeout: 60_000 });

    await cta.click();

    await expect(page.getByText(/incident [\w-]+/i, { exact: false })).toBeVisible({ timeout: 30_000 });
  });
});

