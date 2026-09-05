import { expect, test } from "@playwright/test";
import { assertNoHorizontalOverflow, mockCompletedMix, mockEmptyJobs, mockEmptyLibrary } from "../support";

test.describe("accessible Press Plate workflows", () => {
  test("Process has a named native file input and no premature primary action", async ({ page }) => {
    await page.goto("/process");
    const audioInput = page.getByLabel("Choose audio");
    await expect(audioInput).toBeVisible();
    await expect(audioInput).toHaveAttribute("type", "file");
    await expect(page.getByRole("button", { name: "Start mastering" })).toHaveCount(0);
    // Chromium exposes the native file picker as a button, while the DOM
    // remains a labelled file input. It is the only initial action.
    await expect(page.getByRole("button", { name: "Choose audio" })).toHaveCount(1);
    await expect(page.getByRole("combobox", { name: "Choose mastering character" })).toBeDisabled();
  });

  test("skip link and route navigation give keyboard users a stable destination", async ({ page }) => {
    await page.goto("/process");
    await expect(page.getByRole("heading", { name: "Process audio" })).toBeFocused();
    const skipLink = page.getByRole("link", { name: "Skip to main content" });
    await skipLink.focus();
    await expect(skipLink).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("main")).toBeFocused();
    await page.getByRole("link", { name: "Jobs" }).click();
    await expect(page).toHaveURL(/\/jobs$/);
    await expect(page.getByRole("heading", { name: "Jobs" })).toBeFocused();
    await expect(page.getByRole("link", { name: "Jobs" })).toHaveAttribute("aria-current", "page");
  });

  test("jobs communicate empty state with semantic navigation and no mobile overflow", async ({ page }) => {
    await mockEmptyJobs(page);
    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "No jobs yet" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await assertNoHorizontalOverflow(page, 390);
  });

  test("library empty state and result detail reflow at 390px", async ({ page }) => {
    await mockEmptyLibrary(page);
    await page.goto("/library");
    await expect(page.getByRole("heading", { name: "No completed masters yet" })).toBeVisible();
    await assertNoHorizontalOverflow(page, 390);
    await mockCompletedMix(page);
    await page.goto("/library/mix-1");
    await expect(page.getByRole("heading", { name: "Sound-system transmission" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Compare the real artifacts" })).toBeVisible();
    await assertNoHorizontalOverflow(page, 390);
  });

  test("optional Listening rig is a labelled dialog with focus return and escape", async ({ page }) => {
    await mockCompletedMix(page);
    await page.goto("/library/mix-1");
    const opener = page.getByRole("button", { name: "Open listening rig" });
    await opener.click();
    const dialog = page.getByRole("dialog", { name: "Listening rig" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(page.getByRole("button", { name: "Close rig" })).toBeFocused();
    await expect(page.getByRole("combobox", { name: "Cabinet arrangement" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
  });
});
