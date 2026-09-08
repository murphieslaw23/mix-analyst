import { expect, test } from "@playwright/test";
import { mockCompletedMix } from "../support";

test.describe("reduced-motion listening rig", () => {
  test("marks the optional visual reference reduced when the user requests reduced motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mockCompletedMix(page);
    await page.goto("/library/mix-1");
    await page.getByRole("button", { name: "Open listening rig" }).click();
    await expect(page.getByTestId("rig-panel")).toHaveAttribute("data-motion", "reduced");
    await expect(page.getByText(/remains still when your device requests reduced motion/i)).toBeVisible();
  });

  test("keeps the standard, non-strobing reference explicit when no reduction is requested", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await mockCompletedMix(page);
    await page.goto("/library/mix-1");
    await page.getByRole("button", { name: "Open listening rig" }).click();
    await expect(page.getByTestId("rig-panel")).toHaveAttribute("data-motion", "standard");
    await expect(page.getByRole("img", { name: /speaker reference/i })).toBeVisible();
  });
});
