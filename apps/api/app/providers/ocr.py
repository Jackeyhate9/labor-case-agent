from __future__ import annotations

import base64
import importlib.util
import gc
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image


@dataclass(slots=True)
class OCRRegionResult:
    raw_text: str
    normalized_text: str
    confidence: Decimal | None
    bbox_x: float
    bbox_y: float
    bbox_width: float
    bbox_height: float
    region_type: str = "text"


@dataclass(slots=True)
class OCRPageResult:
    text: str
    width: int | None = None
    height: int | None = None
    regions: list[OCRRegionResult] = field(default_factory=list)


@dataclass(slots=True)
class OCRResult:
    pages: list[OCRPageResult]
    provider: str
    device: str
    warning: str | None = None
    fallback_reasons: list[str] = field(default_factory=list)


class OCRProvider(Protocol):
    name: str

    def availability(self) -> tuple[bool, str]: ...

    def recognize_image(self, path: Path) -> OCRResult: ...


class OllamaOCRProvider:
    name = "ollama-ocr"

    def _configuration(self) -> tuple[str, str]:
        base_url = (
            os.getenv("OLLAMA_OCR_BASE_URL", "").strip()
            or os.getenv("OLLAMA_BASE_URL", "").strip()
            or os.getenv("LLM_BASE_URL", "").strip()
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        model = os.getenv("OLLAMA_OCR_MODEL", "").strip()
        if not model and os.getenv("APP_EDITION", "distribution").strip().lower() == "roadshow":
            model = "unlimitedocrlocal:latest"
        return base_url, model

    def availability(self) -> tuple[bool, str]:
        _, model = self._configuration()
        return (True, "configured") if model else (False, "model_not_configured")

    def recognize_image(self, path: Path) -> OCRResult:
        base_url, model = self._configuration()
        if not model:
            raise RuntimeError("OLLAMA_OCR_MODEL is not configured")
        payload = {
            "model": model,
            "prompt": os.getenv(
                "OLLAMA_OCR_PROMPT",
                "Extract all visible document text faithfully. Return plain text only.",
            ),
            "images": [base64.b64encode(path.read_bytes()).decode("ascii")],
            "stream": False,
        }
        response = httpx.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=float(os.getenv("OLLAMA_OCR_TIMEOUT", "120")),
            follow_redirects=False,
        )
        response.raise_for_status()
        value = response.json()
        text = value.get("response", "") if isinstance(value, dict) else ""
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Ollama OCR returned no text")
        with Image.open(path) as image:
            width, height = image.size
        regions: list[OCRRegionResult] = []
        if importlib.util.find_spec("rapidocr_onnxruntime") is not None:
            try:
                regions = RapidOCRProvider().recognize_image(path).pages[0].regions
            except Exception:
                regions = []
        warning = None if regions else "Ollama OCR returned text without region coordinates"
        return OCRResult(
            [OCRPageResult(text.strip(), width, height, regions)],
            self.name,
            "ollama",
            warning,
        )


class UnlimitedOCRProvider:
    name = "unlimited-ocr"

    def availability(self) -> tuple[bool, str]:
        model_path = os.getenv("UNLIMITED_OCR_MODEL_PATH", "").strip()
        if not model_path or not Path(model_path).is_dir():
            return False, "model_not_installed"
        runtime_path = os.getenv("UNLIMITED_OCR_PYTHON", "").strip()
        if runtime_path and Path(runtime_path).is_file():
            return True, "available_external_runtime"
        if importlib.util.find_spec("torch") is None or importlib.util.find_spec("transformers") is None:
            return False, "python_dependencies_missing"
        try:
            import torch

            if not torch.cuda.is_available():
                return False, "cuda_unavailable_use_cpu_fallback_provider"
        except Exception:
            return False, "cuda_probe_failed"
        return True, "available"

    def recognize_image(self, path: Path) -> OCRResult:
        external_python = Path(os.getenv("UNLIMITED_OCR_PYTHON", ""))
        model_path = os.environ["UNLIMITED_OCR_MODEL_PATH"]
        if external_python.is_file():
            worker = Path(__file__).resolve().parents[1] / "model_workers" / "unlimited_ocr.py"
            completed = subprocess.run(
                [
                    str(external_python),
                    str(worker),
                    "--model",
                    model_path,
                    "--image",
                    str(path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(os.getenv("UNLIMITED_OCR_TIMEOUT", "1800")),
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if completed.returncode != 0:
                message = completed.stderr.strip().splitlines()[-1:] or [
                    "Unlimited OCR worker failed"
                ]
                raise RuntimeError(message[0])
            payload = json.loads(completed.stdout)
            value = payload.get("text", "")
            device = payload.get("device", "external")
        else:
        # Model loading is deliberately lazy: the 3B remote-code model is never
        # imported merely by starting the case-management API.
            from transformers import AutoModel, AutoTokenizer
            import torch

            tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
            model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
                local_files_only=True,
                use_safetensors=True,
                torch_dtype=torch.bfloat16,
            ).eval().cuda()
            output_dir = path.parent / ".unlimited-ocr-output"
            output_dir.mkdir(exist_ok=True)
            try:
                value = model.infer(
                    tokenizer,
                    prompt="<image>document parsing.",
                    image_file=str(path),
                    output_path=str(output_dir),
                    base_size=1024,
                    image_size=640,
                    crop_mode=True,
                    max_length=32768,
                    no_repeat_ngram_size=35,
                    ngram_window=128,
                    save_results=False,
                    eval_mode=True,
                )
                device = "cuda"
            finally:
                # The API may run a different GPU worker (for example MOSS) next.
                # Release this one-shot 3B model instead of retaining the CUDA
                # allocator cache for the lifetime of the web process.
                del model, tokenizer
                gc.collect()
                torch.cuda.empty_cache()
        text = value if isinstance(value, str) else str(value or "")
        with Image.open(path) as image:
            width, height = image.size
        text, regions = _parse_unlimited_output(text, width, height)
        # Some prompts/documents do not emit detection markers. In that case,
        # retain Unlimited-OCR as the text provider and use RapidOCR only for
        # local geometry detection.
        if not regions and importlib.util.find_spec("rapidocr_onnxruntime") is not None:
            try:
                regions = RapidOCRProvider().recognize_image(path).pages[0].regions
            except Exception:
                regions = []
        warning = None if regions else "Unlimited-OCR returned text without region coordinates"
        return OCRResult([OCRPageResult(text=text, width=width, height=height, regions=regions)], self.name, str(device), warning)


_UNLIMITED_REGION = re.compile(
    r"<\|det\|>(?P<kind>.*?)\s*\[\s*(?P<x1>\d+(?:\.\d+)?)\s*,\s*(?P<y1>\d+(?:\.\d+)?)\s*,\s*(?P<x2>\d+(?:\.\d+)?)\s*,\s*(?P<y2>\d+(?:\.\d+)?)\s*\]<\|/det\|>(?P<text>[^\r\n]*)"
)


def _parse_unlimited_output(value: str, width: int, height: int) -> tuple[str, list[OCRRegionResult]]:
    """Convert the model's normalized 0..1000 detections to source pixels."""
    regions: list[OCRRegionResult] = []
    lines: list[str] = []
    for match in _UNLIMITED_REGION.finditer(value):
        raw_text = match.group("text").strip()
        if not raw_text:
            continue
        x1, y1, x2, y2 = (float(match.group(key)) for key in ("x1", "y1", "x2", "y2"))
        scale_x, scale_y = width / 1000.0, height / 1000.0
        regions.append(
            OCRRegionResult(
                raw_text=raw_text,
                normalized_text=raw_text,
                confidence=None,
                bbox_x=max(0.0, min(width, x1 * scale_x)),
                bbox_y=max(0.0, min(height, y1 * scale_y)),
                bbox_width=max(0.0, min(width, x2 * scale_x) - max(0.0, x1 * scale_x)),
                bbox_height=max(0.0, min(height, y2 * scale_y) - max(0.0, y1 * scale_y)),
                region_type=match.group("kind").strip() or "text",
            )
        )
        lines.append(raw_text)
    return ("\n".join(lines) if lines else value.strip()), regions


class PaddleOCRProvider:
    name = "paddleocr"

    def availability(self) -> tuple[bool, str]:
        return (True, "available") if importlib.util.find_spec("paddleocr") else (False, "package_not_installed")

    def recognize_image(self, path: Path) -> OCRResult:
        from paddleocr import PaddleOCR

        engine = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
        prediction = engine.predict(str(path))
        regions: list[OCRRegionResult] = []
        lines: list[str] = []
        for page in prediction:
            data = page.json.get("res", page.json) if hasattr(page, "json") else page
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            boxes = data.get("rec_polys", [])
            for text, score, box in zip(texts, scores, boxes):
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                lines.append(str(text))
                regions.append(OCRRegionResult(str(text), str(text).strip(), Decimal(str(score)), min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
        with Image.open(path) as image:
            width, height = image.size
        return OCRResult([OCRPageResult("\n".join(lines), width, height, regions)], self.name, "gpu_or_cpu")


class WindowsOCRProvider:
    name = "windows-ocr"

    def availability(self) -> tuple[bool, str]:
        if os.name != "nt":
            return False, "not_windows"
        if importlib.util.find_spec("winrt") is None:
            return False, "winrt_package_not_installed"
        return True, "available"

    def recognize_image(self, path: Path) -> OCRResult:
        raise RuntimeError("Windows OCR adapter is installed but not configured")


class RapidOCRProvider:
    name = "rapidocr"

    def availability(self) -> tuple[bool, str]:
        return (True, "available") if importlib.util.find_spec("rapidocr_onnxruntime") else (False, "package_not_installed")

    def recognize_image(self, path: Path) -> OCRResult:
        from rapidocr_onnxruntime import RapidOCR

        result, _ = RapidOCR()(str(path))
        with Image.open(path) as image:
            width, height = image.size
        if not result:
            return OCRResult([OCRPageResult("", width, height)], self.name, "cpu", "OCR completed but no text was recognized; manual transcription is required")
        lines: list[str] = []
        regions: list[OCRRegionResult] = []
        for box, text, confidence in result:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            raw_text = str(text)
            lines.append(raw_text)
            regions.append(
                OCRRegionResult(
                    raw_text=raw_text,
                    normalized_text=raw_text.strip(),
                    confidence=Decimal(str(confidence)),
                    bbox_x=min(xs),
                    bbox_y=min(ys),
                    bbox_width=max(xs) - min(xs),
                    bbox_height=max(ys) - min(ys),
                )
            )
        return OCRResult([OCRPageResult("\n".join(lines), width, height, regions)], self.name, "cpu")


class OCRRouter:
    def __init__(self, providers: list[OCRProvider] | None = None):
        if providers is not None:
            self.providers = providers
            return
        catalog: dict[str, OCRProvider] = {
            "rapidocr": RapidOCRProvider(),
            "paddleocr": PaddleOCRProvider(),
            "windows-ocr": WindowsOCRProvider(),
            "unlimited-ocr": UnlimitedOCRProvider(),
            "ollama-ocr": OllamaOCRProvider(),
        }
        selected = os.getenv("OCR_PROVIDER", "auto").strip().lower()
        if selected == "ollama-ocr":
            self.providers = [catalog["ollama-ocr"], catalog["rapidocr"]]
        elif selected in catalog:
            self.providers = [catalog[selected]]
        elif selected == "disabled":
            self.providers = []
        else:
            # v0.2 priority: highest-quality local model first, then progressively
            # lighter CPU fallbacks when the model/GPU is unavailable.
            self.providers = [
                catalog[name]
                for name in (
                    "unlimited-ocr",
                    "ollama-ocr",
                    "paddleocr",
                    "windows-ocr",
                    "rapidocr",
                )
            ]

    def recognize_image(self, path: Path) -> OCRResult:
        reasons: list[str] = []
        for provider in self.providers:
            available, reason = provider.availability()
            if not available:
                reasons.append(f"{provider.name}:{reason}")
                continue
            try:
                result = provider.recognize_image(path)
                result.fallback_reasons = reasons
                return result
            except Exception as exc:
                reasons.append(f"{provider.name}:failed:{type(exc).__name__}")
        return OCRResult(
            pages=[OCRPageResult("")],
            provider="unavailable",
            device="none",
            warning="All local OCR providers are unavailable or failed; manual transcription is required",
            fallback_reasons=reasons,
        )
