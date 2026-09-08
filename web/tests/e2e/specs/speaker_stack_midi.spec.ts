import { expect, test } from "@playwright/test";
import { mockCompletedMix } from "../support";

test.describe("optional listening rig", () => {
  test("does not load the retired canvas or MIDI controls before a result is opened", async ({ page }) => {
    await page.goto("/process");
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /MIDI/i })).toHaveCount(0);
  });

  test("offers a keyboard-operable cabinet arrangement in the lazy listening rig", async ({ page }) => {
    await mockCompletedMix(page);
    await page.goto("/library/mix-1");
    await page.getByRole("button", { name: "Open listening rig" }).click();
    const cabinet = page.getByRole("combobox", { name: "Cabinet arrangement" });
    await cabinet.selectOption("wall");
    await expect(cabinet).toHaveValue("wall");
    await expect(page.getByRole("img", { name: "wall speaker reference" })).toBeVisible();
  });
});
