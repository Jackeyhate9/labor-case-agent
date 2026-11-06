import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceChain } from "@/components/evidence-chain";
describe("四层证据链", () => {
  it("始终按事实流转顺序展示四层", () => {
    render(<EvidenceChain active="confirmed" />);
    expect(screen.getByLabelText("四层证据链")).toHaveTextContent("原始材料");
    expect(screen.getByText("机器提取")).toBeInTheDocument();
    expect(screen.getByText("用户确认")).toBeInTheDocument();
    expect(screen.getByText("文书")).toBeInTheDocument();
  });
});
