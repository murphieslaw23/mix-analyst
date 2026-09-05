import { expect, test } from "@playwright/test";

test.describe("Press Plate app shell", () => {
  test("mobile navigation reaches every primary destination without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/process");
    for (const [label, path, heading] of [["Jobs", "/jobs", "Jobs"], ["Library", "/library", "Library"], ["More", "/more", "More"], ["Process", "/process", "Process audio"]] as const) {
      await page.getByRole("link", { name: label }).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.getByRole("heading", { name: heading })).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    }
  });
  test("primary controls meet a 44 pixel mobile touch target", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/process");
    for (const label of ["Process", "Jobs", "Library", "More"]) {
      const box = await page.getByRole("link", { name: label }).boundingBox();
      expect(box).not.toBeNull();
      expect(box?.width).toBeGreaterThanOrEqual(44);
      expect(box?.height).toBeGreaterThanOrEqual(44);
    }
  });
});
