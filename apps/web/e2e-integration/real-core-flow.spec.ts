import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

test("真实后端：建案、OCR、事实、时间线、工资、工作流、文书与 ZIP", async ({
  page,
}) => {
  const provider = await page.request.patch(
    "http://127.0.0.1:8000/api/system/settings",
    { data: { ocr_provider: "rapidocr" } },
  );
  expect(provider.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("link", { name: "新建案件", exact: true }).click();
  await page.getByLabel("劳动者称呼").fill("测试用户甲");
  await page.getByLabel("用人单位").fill("北京某某文化传媒有限公司（虚构）");
  await page.getByRole("button", { name: /下一步/ }).click();
  await page.getByLabel("开始工作日期").fill("2024-07-01");
  await page.getByLabel("结束日期（可空）").fill("2026-06-30");
  await page.getByLabel("约定月工资（元）").fill("6000");
  await page.getByRole("button", { name: /下一步/ }).click();
  await page
    .getByLabel("请用自己的话描述")
    .fill(
      "2026年2月仅收到第三人代付1000元，之后欠薪；6月社保停缴。完全虚构测试数据。",
    );
  await page.getByRole("button", { name: /下一步/ }).click();
  await page.getByText("支付拖欠工资").click();
  await page.getByRole("button", { name: "建立案件卷宗" }).click();
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}/);
  const caseId = page.url().match(/\/cases\/([0-9a-f-]{36})/)?.[1];
  expect(caseId).toBeTruthy();

  const caseResponse = await page.request.get(
    `http://127.0.0.1:8000/api/cases/${caseId}`,
  );
  expect(caseResponse.ok()).toBeTruthy();
  const casePayload = await caseResponse.json();
  expect(casePayload.data.parties).toHaveLength(2);

  await page.goto(`/cases/${caseId}/evidence`);
  const screenshot = path.resolve(
    process.cwd(),
    "../../samples/demo-case/chat-01.png",
  );
  await page.locator('input[type="file"]').setInputFiles(screenshot);
  const evidence = page.getByRole("button", { name: /chat-01\.png/ });
  await expect(evidence).toBeVisible();
  await evidence.click();
  await page.getByRole("button", { name: /运行解析/ }).click();
  await expect(page.getByText(/工资暂按每月6000元/)).toBeVisible({
    timeout: 60_000,
  });

  await page.getByRole("link", { name: "事实确认" }).click();
  const confirm = page
    .getByRole("button", { name: "确认", exact: true })
    .first();
  await expect(confirm).toBeVisible();
  await confirm.click();
  await expect(page.getByText("用户已确认").first()).toBeVisible();

  await page.getByRole("link", { name: "时间线" }).click();
  await page.getByRole("button", { name: /重建时间线/ }).click();
  await expect(page.locator(".timeline article").first()).toBeVisible();

  await page.getByRole("link", { name: "工资明细" }).click();
  await page.getByLabel("工资期间").fill("2026-02");
  await page.getByLabel("应发金额").fill("6000");
  await page.getByLabel("实际支付").fill("1000");
  await page.getByLabel("支付方式").selectOption("third_party");
  await page.getByRole("button", { name: /保存工资记录/ }).click();
  await expect(page.getByText("¥5000.00").first()).toBeVisible();

  await page.getByRole("link", { name: "证据缺口" }).click();
  await page.getByRole("button", { name: "开始运行" }).click();
  await expect(page.getByText("employment_start")).toBeVisible();

  await page.getByRole("link", { name: "抗辩模拟" }).click();
  await page.getByRole("button", { name: "开始运行" }).click();
  await expect(page.getByText(/项目合作/).first()).toBeVisible();

  await page.getByRole("link", { name: "文书" }).click();
  await page.getByRole("button", { name: "生成新版本" }).click();
  await expect(page.getByText(/版本 v1/)).toBeVisible();

  const screenshotDirectory = path.resolve(process.cwd(), "../../docs/images");
  fs.mkdirSync(screenshotDirectory, { recursive: true });
  await page.screenshot({
    path: path.join(screenshotDirectory, "labor-case-workspace.png"),
    fullPage: true,
  });

  await page.getByRole("link", { name: "导出档案" }).click();
  await page.getByRole("button", { name: /生成ZIP导出/ }).click();
  const downloadLink = page.getByRole("link", { name: "下载已生成文件" });
  await expect(downloadLink).toBeVisible({ timeout: 60_000 });
  const downloadPromise = page.waitForEvent("download");
  await downloadLink.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.zip$/);

  await page.getByRole("link", { name: "系统自检" }).click();
  await expect(page.getByText("failed", { exact: true })).toHaveCount(0);
  await expect(page.getByText("ocr_provider")).toBeVisible();
});
