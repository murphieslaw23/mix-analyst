import { expect, test } from "@playwright/test";

const fixtureToken = "aaa.bbb.ccc";

test("fragment bootstrap strips the token and authorizes API requests", async ({ page }) => {
  let authorization: string | null = null;
  await page.route("**/api/v1/mixes", async (route) => {
    authorization = route.request().headers()["authorization"] ?? null;
    await route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } });
  });

  await page.goto(`/library#access_token=${fixtureToken}`);
  await expect(page.getByRole("heading", { name: "No completed masters yet" })).toBeVisible();
  await expect.poll(() => authorization).toBe(`Bearer ${fixtureToken}`);
  await expect(page).toHaveURL(/\/library$/);
  expect(await page.evaluate(() => window.location.hash)).toBe("");
  expect(await page.evaluate(() => window.sessionStorage.getItem("syco23:api-access-token:v1"))).toBe(fixtureToken);
});

test("non-API browser requests never receive the bearer credential", async ({ page }) => {
  let assetAuthorization: string | null = "not-observed";
  await page.route("**/api/v1/mixes", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } });
  });
  await page.route("**/auth-transport-probe.txt", async (route) => {
    assetAuthorization = route.request().headers()["authorization"] ?? null;
    await route.fulfill({ body: "ok", contentType: "text/plain" });
  });

  await page.goto(`/library#access_token=${fixtureToken}`);
  await page.evaluate(async () => {
    await fetch("/auth-transport-probe.txt");
  });
  expect(assetAuthorization).toBeNull();
});
