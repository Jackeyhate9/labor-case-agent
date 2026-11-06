import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { EvidencePreview } from "@/components/evidence-preview";


test("clicking OCR text highlights the matching image region", () => {
  render(
    <EvidencePreview
      preview={{ kind: "image", content_url: "/api/evidence/ev-1/content" }}
      pages={[
        {
          id: "page-1",
          page_number: 1,
          width: 1000,
          height: 2000,
          regions: [
            {
              id: "region-1",
              raw_text: "工资暂按每月6000元",
              bbox_x: 100,
              bbox_y: 300,
              bbox_width: 400,
              bbox_height: 80,
              confidence: 0.98,
            },
          ],
        },
      ]}
      segments={[]}
    />,
  );

  fireEvent.click(
    within(screen.getByLabelText("OCR 文本定位轨")).getByRole("button", {
      name: /工资暂按每月6000元/,
    }),
  );
  expect(screen.getByTestId("region-region-1")).toHaveAttribute("data-active", "true");
  expect(screen.getByAltText("证据原件预览")).toBeInTheDocument();
});
