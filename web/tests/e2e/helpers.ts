import { expect, type Page } from '@playwright/test';

/**
 * Shared responsive guard (Product UI Task 6): the document must never
 * scroll horizontally at the given viewport width.
 */
export async function assertNoHorizontalOverflow(page: Page, width: number): Promise<void> {
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth).toBeLessThanOrEqual(width);
}
