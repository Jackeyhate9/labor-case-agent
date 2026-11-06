import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-integration",
  workers: 1,
  timeout: 300_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "python -m alembic -c ../api/alembic.ini upgrade head && python -m uvicorn app.main:app --app-dir ../api --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/system/health",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        ...process.env,
        DATABASE_URL: "sqlite:///../../tmp/playwright-v02-integration.db",
        STORAGE_ROOT: "../../tmp/playwright-v02-cases",
        SYSTEM_SETTINGS_FILE: "../../tmp/playwright-v02-settings.json",
        MAX_UPLOAD_BYTES: String(5 * 1024 * 1024),
        LLM_PROVIDER: "disabled",
        OCR_PROVIDER: "unlimited-ocr",
        AUDIO_PROVIDER: "moss-transcribe-diarize",
        UNLIMITED_OCR_MODEL_PATH: "../../models/Unlimited-OCR",
        MOSS_PYTHON: "../../.venv-moss/Scripts/python.exe",
        MOSS_MODEL_PATH: "../../models/MOSS-Transcribe-Diarize",
        MOSS_TRANSCRIBE_TIMEOUT: "1800",
        CORS_ORIGINS: "http://127.0.0.1:3000,http://localhost:3000",
      },
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        ...process.env,
        NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});
