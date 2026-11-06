"use client";

import { ChevronLeft, ChevronRight, Crosshair, Play } from "lucide-react";
import type { PDFDocumentLoadingTask } from "pdfjs-dist";
import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

export type OCRRegion = {
  id: string;
  raw_text: string;
  bbox_x: number;
  bbox_y: number;
  bbox_width: number;
  bbox_height: number;
  confidence?: number | null;
};

export type OCRPage = {
  id: string;
  page_number: number;
  width?: number | null;
  height?: number | null;
  ocr_text?: string;
  regions?: OCRRegion[];
};

export type AudioSegment = {
  id: string;
  speaker_id: string;
  start_time: string | number;
  end_time: string | number;
  text: string;
};

export type PreviewData = {
  kind: "image" | "pdf" | "document" | "table" | "audio" | "text";
  content_url: string;
  html?: string;
  text?: string;
  sheets?: Array<{ name: string; rows: string[][] }>;
  truncated?: boolean;
};

const absoluteUrl = (path: string) =>
  path.startsWith("http") ? path : `${API_BASE}${path}`;

function RegionLayer({
  page,
  selected,
  onSelect,
}: {
  page?: OCRPage;
  selected?: string;
  onSelect: (id: string) => void;
}) {
  if (!page?.width || !page?.height) return null;
  const pageWidth = page.width;
  const pageHeight = page.height;
  return (
    <div className="region-layer" aria-label="OCR 区域定位层">
      {page.regions?.map((region) => (
        <button
          key={region.id}
          type="button"
          aria-label={`定位：${region.raw_text}`}
          aria-pressed={selected === region.id}
          data-testid={`region-${region.id}`}
          data-active={selected === region.id ? "true" : "false"}
          className={`region-box ${selected === region.id ? "active" : ""}`}
          style={{
            left: `${(region.bbox_x / pageWidth) * 100}%`,
            top: `${(region.bbox_y / pageHeight) * 100}%`,
            width: `${(region.bbox_width / pageWidth) * 100}%`,
            height: `${(region.bbox_height / pageHeight) * 100}%`,
          }}
          onClick={() => onSelect(region.id)}
        />
      ))}
    </div>
  );
}

function PdfPage({ url, pageNumber }: { url: string; pageNumber: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    let task: PDFDocumentLoadingTask | undefined;
    (async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();
        task = pdfjs.getDocument({ url });
        const document = await task.promise;
        const page = await document.getPage(pageNumber);
        const viewport = page.getViewport({ scale: 1.5 });
        const target = canvas.current;
        if (!target || cancelled) return;
        target.width = viewport.width;
        target.height = viewport.height;
        const context = target.getContext("2d");
        if (!context) throw new Error("Canvas 2D unavailable");
        await page.render({ canvas: target, canvasContext: context, viewport }).promise;
      } catch (reason) {
        if (!cancelled)
          setError(reason instanceof Error ? reason.message : "PDF 无法渲染");
      }
    })();
    return () => {
      cancelled = true;
      void task?.destroy();
    };
  }, [url, pageNumber]);
  return error ? (
    <p className="preview-error">PDF 预览失败：{error}</p>
  ) : (
    <canvas ref={canvas} aria-label={`PDF 第 ${pageNumber} 页`} />
  );
}

export function EvidencePreview({
  preview,
  pages,
  segments,
}: {
  preview: PreviewData;
  pages: OCRPage[];
  segments: AudioSegment[];
}) {
  const [pageNumber, setPageNumber] = useState(1);
  const [selected, setSelected] = useState<string>();
  const [selectedSegment, setSelectedSegment] = useState<string>();
  const audio = useRef<HTMLAudioElement>(null);
  const page = pages.find((item) => item.page_number === pageNumber) ?? pages[0];
  const regions = page?.regions ?? [];
  const url = absoluteUrl(preview.content_url);
  const pageCount = Math.max(pages.length, 1);
  const selectedRegion = useMemo(
    () => regions.find((region) => region.id === selected),
    [regions, selected],
  );

  const visual =
    preview.kind === "image" || preview.kind === "pdf" ? (
      <div className="evidence-canvas-wrap">
        <div className="evidence-canvas">
          {preview.kind === "image" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt="证据原件预览" />
          ) : (
            <PdfPage url={url} pageNumber={pageNumber} />
          )}
          <RegionLayer page={page} selected={selected} onSelect={setSelected} />
        </div>
      </div>
    ) : preview.kind === "document" ? (
      <article
        className="document-preview"
        aria-label="文档派生预览"
        dangerouslySetInnerHTML={{ __html: preview.html ?? "" }}
      />
    ) : preview.kind === "table" ? (
      <div className="table-preview">
        {preview.sheets?.map((sheet) => (
          <section key={sheet.name}>
            <h4>{sheet.name}</h4>
            <table>
              <tbody>
                {sheet.rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row.map((cell, columnIndex) => (
                      <td key={columnIndex}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
        {preview.truncated && <p className="form-note">仅显示前 200 行、50 列。</p>}
      </div>
    ) : preview.kind === "audio" ? (
      <div className="audio-preview">
        <audio ref={audio} controls preload="metadata" src={url}>
          浏览器无法播放该音频。
        </audio>
        <div className="audio-segments" aria-label="时间戳转写">
          {segments.map((segment) => (
            <button
              type="button"
              key={segment.id}
              aria-pressed={selectedSegment === segment.id}
              className={selectedSegment === segment.id ? "active" : ""}
              onClick={() => {
                if (!audio.current) return;
                setSelectedSegment(segment.id);
                audio.current.currentTime = Number(segment.start_time);
                void audio.current.play().catch(() => undefined);
              }}
            >
              <Play size={14} />
              <code>
                {Number(segment.start_time).toFixed(2)}–
                {Number(segment.end_time).toFixed(2)}
              </code>
              <strong>{segment.speaker_id}</strong>
              <span>{segment.text}</span>
            </button>
          ))}
        </div>
      </div>
    ) : (
      <pre className="text-preview">{preview.text}</pre>
    );

  return (
    <div className="evidence-locator">
      <section className="preview-source">
        {pages.length > 1 && (
          <nav className="page-controls" aria-label="证据页码">
            <button
              type="button"
              aria-label="上一页"
              disabled={pageNumber <= 1}
              onClick={() => {
                setPageNumber((number) => number - 1);
                setSelected(undefined);
              }}
            >
              <ChevronLeft size={16} />
            </button>
            <span>
              第 {pageNumber} / {pageCount} 页
            </span>
            <button
              type="button"
              aria-label="下一页"
              disabled={pageNumber >= pageCount}
              onClick={() => {
                setPageNumber((number) => number + 1);
                setSelected(undefined);
              }}
            >
              <ChevronRight size={16} />
            </button>
          </nav>
        )}
        {visual}
      </section>
      {(preview.kind === "image" || preview.kind === "pdf") && (
        <aside className="locator-rail" aria-label="OCR 文本定位轨">
          <header>
            <Crosshair size={16} />
            <strong>页内定位</strong>
            <span>{regions.length} 个区域</span>
          </header>
          {regions.map((region, index) => (
            <button
              type="button"
              key={region.id}
              className={selected === region.id ? "active" : ""}
              aria-pressed={selected === region.id}
              onClick={() => setSelected(region.id)}
            >
              <code>{String(index + 1).padStart(2, "0")}</code>
              <span>{region.raw_text}</span>
              {region.confidence != null && (
                <small>{Math.round(region.confidence * 100)}%</small>
              )}
            </button>
          ))}
          {selectedRegion && (
            <a href={`${API_BASE}/api/regions/${selectedRegion.id}/crop`} target="_blank">
              打开区域裁剪
            </a>
          )}
        </aside>
      )}
    </div>
  );
}
