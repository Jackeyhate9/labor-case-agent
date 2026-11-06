import { expect, test } from "@playwright/test";
test("首页到新建案件向导核心流程", async ({ page }) => {
  const corsHeaders = {
    "access-control-allow-origin": "http://127.0.0.1:3000",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
  };
  await page.route("**/api/system/health", (r) =>
    r.fulfill({ headers: corsHeaders, json: { status: "ok" } }),
  );
  await page.route("**/api/cases", async (r) => {
    if (r.request().method() === "OPTIONS") {
      await r.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    if (r.request().method() === "POST")
      await r.fulfill({ headers: corsHeaders, json: { data: { id: "CASE-E2E" } } });
    else await r.fulfill({ headers: corsHeaders, json: { data: [] } });
  });
  await page.route("**/api/cases/*/claims", async (r) => {
    if (r.request().method() === "OPTIONS") {
      await r.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    await r.fulfill({ headers: corsHeaders, json: { data: { id: "CLAIM-E2E" } } });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /把散落的证据/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "新建案件", exact: true }).click();
  await page.getByLabel("劳动者称呼").fill("测试用户甲");
  await page.getByLabel("用人单位").fill("某某文化传媒有限公司（虚构）");
  await page.getByRole("button", { name: /下一步/ }).click();
  await page.getByRole("button", { name: /下一步/ }).click();
  await page
    .getByLabel("请用自己的话描述")
    .fill("2026年2月开始部分拖欠工资，社保于5月停缴。");
  await page.getByRole("button", { name: /下一步/ }).click();
  await page.getByText("支付拖欠工资").click();
  await page.getByRole("button", { name: "建立案件卷宗" }).click();
  await expect(page).toHaveURL(/cases\/CASE-E2E/);
});
