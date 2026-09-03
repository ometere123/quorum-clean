import { test, expect } from "@playwright/test";

test.describe("Quorum Clean served production build", () => {
  test("labels fixture mode and exposes the complete action rail", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("BUNDLED FIXTURES")).toBeVisible();
    await expect(page.getByText("No fixture has been substituted.")).toHaveCount(0);
    await page.goto("/manage");
    await expect(page.getByRole("button", { name: "Connect wallet" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Open round" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Register participant" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Declare GitHub scope" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Request screening" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Screen / lock" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Appeal / adjudicate" })).toBeVisible();
  });

  test("a missing injected wallet is a visible refusal, not a fixture fallback", async ({ page }) => {
    await page.goto("/manage");
    await page.getByRole("button", { name: "Connect wallet" }).click();
    // Shown twice: once beside the header button that was clicked, once as the standing
    // gate note on the write panel below. Both say the same true thing, so either is fine.
    await expect(page.getByText("No injected wallet was found in this browser.").first()).toBeVisible();
  });
});
