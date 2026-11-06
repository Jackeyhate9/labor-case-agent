import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000";

async function createCase(page: Page, title: string) {
  const response = await page.request.post(`${API}/api/cases`, {
    data: {
      title,
      parties: [{ party_type: "worker", name: "测试劳动者" }],
    },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).data.id as string;
}

test("v0.2 image: upload, Unlimited-OCR, locate region, confirm fact", async ({ page }) => {
  const provider = await page.request.patch(`${API}/api/system/settings`, {
    data: { ocr_provider: "unlimited-ocr" },
  });
  expect(provider.ok()).toBeTruthy();
  const caseId = await createCase(page, "v0.2 图片证据流程");
  await page.goto(`/cases/${caseId}/evidence`);
  await page.locator('input[type="file"]').setInputFiles(
    path.resolve(process.cwd(), "../../samples/demo-case/chat-01.png"),
  );
  const item = page.getByRole("button", { name: /chat-01\.png/ });
  await expect(item).toBeVisible();
  await item.click();
  await expect(page.getByAltText("证据原件预览")).toBeVisible();
  await page.getByRole("button", { name: "运行解析" }).click();
  const locator = page.getByLabel("OCR 文本定位轨");
  await expect(locator.getByRole("button").first()).toBeVisible({ timeout: 180_000 });
  await locator.getByRole("button").first().click();
  await expect(page.locator('[data-active="true"]').first()).toBeVisible();
  await page.screenshot({
    path: path.resolve(process.cwd(), "../../docs/images/v02-evidence-locator.png"),
    fullPage: true,
  });

  await page.getByRole("link", { name: "事实确认" }).click();
  const confirm = page.getByRole("button", { name: "确认", exact: true }).first();
  await expect(confirm).toBeVisible();
  await confirm.click();
  await expect(page.getByText("用户已确认").first()).toBeVisible();
});

test("v0.2 audio: upload, MOSS transcription, play timestamp, create facts", async ({ page }) => {
  const provider = await page.request.patch(`${API}/api/system/settings`, {
    data: { audio_provider: "moss-transcribe-diarize" },
  });
  expect(provider.ok()).toBeTruthy();
  const caseId = await createCase(page, "v0.2 音频证据流程");
  await page.goto(`/cases/${caseId}/evidence`);
  await page.locator('input[type="file"]').setInputFiles(
    path.resolve(process.cwd(), "../../samples/demo-case/wage-call.wav"),
  );
  const item = page.getByRole("button", { name: /wage-call\.wav/ });
  await expect(item).toBeVisible();
  await item.click();
  await expect(page.locator("audio")).toBeVisible();
  await page.getByRole("button", { name: "运行解析" }).click();
  const segment = page.getByLabel("时间戳转写").getByRole("button").first();
  await expect(segment).toBeVisible({ timeout: 180_000 });
  await segment.click();
  await expect(segment).toHaveAttribute("aria-pressed", "true");
  await expect
    .poll(() => page.locator("audio").evaluate((node: HTMLAudioElement) => node.currentTime))
    .toBeGreaterThan(0);

  const facts = await page.request.get(`${API}/api/cases/${caseId}/facts`);
  expect(facts.ok()).toBeTruthy();
  const payload = await facts.json();
  expect(payload.data.length).toBeGreaterThan(0);
  expect(payload.data.some((fact: { source_audio_segment_id?: string }) => fact.source_audio_segment_id)).toBeTruthy();
});

test("v0.2 export: complete case archive remains downloadable", async ({ page }) => {
  const caseId = await createCase(page, "v0.2 完整导出流程");
  const upload = await page.request.post(`${API}/api/cases/${caseId}/evidence`, {
    multipart: {
      file: {
        name: "wage-note.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("2026年2月拖欠工资6000元，虚构测试材料。", "utf8"),
      },
    },
  });
  const evidenceId = (await upload.json()).data.id;
  await page.request.post(`${API}/api/evidence/${evidenceId}/process`);

  await page.goto(`/cases/${caseId}/export`);
  await page.getByRole("button", { name: "生成ZIP导出" }).click();
  const link = page.getByRole("link", { name: "下载已生成文件" });
  await expect(link).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
});
