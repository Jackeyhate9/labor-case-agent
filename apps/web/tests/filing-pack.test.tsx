import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExportView } from "@/components/case-workspace";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  getCase: vi.fn(),
}));

describe("线下立案材料包", () => {
  beforeEach(() => {
    vi.mocked(api)
      .mockResolvedValueOnce({ filename: "offline-filing-pack.zip" })
      .mockResolvedValueOnce(new Blob(["zip"]));
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:filing-pack"),
    });
  });

  it("说明地方适用边界并生成可下载预填包", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ExportView caseId="case-1" />
      </QueryClientProvider>,
    );

    expect(screen.getByText("线下立案材料包")).toBeInTheDocument();
    expect(screen.getByText(/以拟提交仲裁机构最新要求为准/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /生成线下预填包/ }));

    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/api/cases/case-1/filing-pack", {
        method: "POST",
      }),
    );
    expect(await screen.findByRole("link", { name: /下载线下立案材料包/ })).toHaveAttribute(
      "download",
      "offline-filing-pack.zip",
    );
  });
});
