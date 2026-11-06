# Unlimited‑OCR 安装、路由与实测

上游模型：[baidu/Unlimited-OCR](https://huggingface.co/baidu/Unlimited-OCR)，许可证为 MIT。模型使用 `trust_remote_code`；只应从可信 revision 下载并先核对 `dist/models/checksums.sha256`。

## 安装与下载

官方 Transformers 示例以 Python 3.12、CUDA 12.9、PyTorch 2.10、Transformers 4.57.1 为基线。本项目实测环境为 Windows、Python 3.11、CUDA build 的 PyTorch 2.12 dev、Transformers 4.57.1。源码模式可执行：

```powershell
python -m pip install "torch>=2.10" "transformers==4.57.1" pillow einops addict easydict pymupdf psutil
huggingface-cli download baidu/Unlimited-OCR --local-dir models/Unlimited-OCR
$env:UNLIMITED_OCR_MODEL_PATH = (Resolve-Path models/Unlimited-OCR)
$env:OCR_PROVIDER = "unlimited-ocr"   # 或 auto
```

`dist/models/Unlimited-OCR` 已附带本次验收使用的权重。Windows 安装后可复制到 `%LOCALAPPDATA%\LaborCaseAgent\models\Unlimited-OCR`；但 NSIS 的 RapidOCR sidecar 不内置 PyTorch/CUDA，Unlimited‑OCR 仍需源码/独立兼容运行时。

## 路由与坐标

`OCRRouter` 的 `auto` 顺序为 Unlimited‑OCR → PaddleOCR → Windows OCR → RapidOCR。Unlimited 模型不可用、CUDA 不可用或推理失败时会记录原因并继续降级；所有 provider 都失败时明确返回人工录入提示，不生成伪造 OCR。

调用使用 `eval_mode=True` 取得真实文本，并解析模型的 `<|det|>…[x1,y1,x2,y2]`（0–1000）标记为原图像素坐标。模型没有返回检测标记时，才使用 RapidOCR 做本地几何检测。一次推理结束后显式释放 CUDA cache，避免阻塞后续 MOSS worker。

## 2026‑07‑22 性能实测

| 项目 | 结果 |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5090 Laptop，24,463 MiB |
| 权重磁盘占用 | 6.31 GiB |
| 测试输入 | `samples/demo-case/chat-01.png`，虚构聊天截图 |
| 冷启动推理 | 40.3 秒；Playwright 完整图片流程 46.1 秒 |
| 输出 | 684 字符；模型原生检测 + 路由持久化 11 个区域（E2E 页面显示 8 个有效文本区域） |
| 观察到的进程显存 | 约 12.25 GiB 峰值；完成后释放 |
| CPU fallback | RapidOCR 对两张样例分别 4.71 秒、3.65 秒，均为真实 ONNX 推理 |

这些数字只代表本机冷启动，不是准确率基准。低清图片、手写体、复杂表格和不同驱动可能显著改变结果；所有文本、框和事实都必须人工复核。

## Windows 分发边界

最终安装器采用 `rapidocr` profile，能离线执行 CPU OCR。四套大型权重作为 `dist/models` 独立载荷（147 个文件、约 14.43 GiB，带逐文件 SHA‑256），没有塞入 500 MB 级安装器，也不会隐式联网下载。
