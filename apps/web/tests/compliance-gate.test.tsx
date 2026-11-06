import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ComplianceGate } from "@/components/compliance-gate";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

const status = {
  acceptance_required: true,
  accepted: false,
  versions: {
    terms: "2026-07-29-v1",
    privacy: "2026-07-29-v1",
    ai_notice: "2026-07-29-v1",
  },
  publisher: { name: "测试发行方", support_email: "support@example.test", configured: true },
  documents: [
    { id: "terms", title: "用户服务协议", href: "/legal/terms" },
    { id: "privacy", title: "隐私政策", href: "/legal/privacy" },
    { id: "ai-notice", title: "AI 与自动化处理说明", href: "/legal/ai-notice" },
  ],
};

function response(data: unknown) {
  return new Response(JSON.stringify({ data }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("ComplianceGate", () => {
  afterEach(() => vi.restoreAllMocks());

  it("要求逐项确认当前协议版本后才进入工作台", async () => {
    let accepted = false;
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") accepted = true;
      return response(
        accepted ? { ...status, acceptance_required: false, accepted: true } : status,
      );
    });
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ComplianceGate><p>案件工作台内容</p></ComplianceGate>
      </QueryClientProvider>,
    );

    const accept = await screen.findByRole("button", { name: "接受当前版本并进入工作台" });
    expect(accept).toBeDisabled();
    for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
    fireEvent.click(accept);

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/compliance/accept"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"terms_version":"2026-07-29-v1"'),
        }),
      ),
    );
    expect(await screen.findByText("案件工作台内容")).toBeInTheDocument();
  });
});
