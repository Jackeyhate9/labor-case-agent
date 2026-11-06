import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
describe("API 客户端", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
    window.history.replaceState(null, "", "/");
  });
  it("解包统一 data 响应", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { id: "CASE-1" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(api("/api/cases/CASE-1")).resolves.toEqual({ id: "CASE-1" });
  });
  it("向界面传递后端错误信息", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "OCR 服务不可用" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(api("/api/system/health")).rejects.toMatchObject<ApiError>({
      status: 503,
      message: "OCR 服务不可用",
    });
  });

  it("从桌面启动片段接收会话令牌并从地址栏移除", async () => {
    window.history.replaceState(null, "", "/#app_session=desktop-secret");
    const request = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { status: "healthy" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await api("/api/system/health");

    const [url, options] = request.mock.calls[0];
    expect(String(url)).toContain("/api/system/health");
    expect(options?.credentials).toBe("include");
    expect(new Headers(options?.headers).get("X-App-Session")).toBe(
      "desktop-secret",
    );
    expect(window.location.hash).toBe("");
    expect(window.sessionStorage.getItem("labor-case-session")).toBe(
      "desktop-secret",
    );
  });
});
