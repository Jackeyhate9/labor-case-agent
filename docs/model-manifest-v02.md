# v0.2 模型清单审计

仓库 `models/manifest.json` 声明了以下可选模型：

| 模型 | 声明用途 | 声明许可证 | v0.2 是否打包/验证 |
| --- | --- | --- | --- |
| `baidu/Unlimited-OCR` | OCR | MIT | RTX 5090 实测成功 |
| `OpenMOSS-Team/MOSS-Transcribe-Diarize` | 转写/说话人分离 | Apache-2.0 | 实测成功 |
| `BAAI/bge-m3` | 向量嵌入 | MIT | 实测成功 |
| `nvidia/Nemotron-3-Embed-1B-BF16` | 向量嵌入 | OpenMDW-1.1 | 实测成功 |

`dist/models` 已复制 147 个模型文件（约 14.43 GB）并提供 checksums。仓库清单本身仍没有不可变上游 revision 或下载 URL；许可证字段需要对实际下载 revision 继续复核。

NSIS 安装器不内嵌上述 14.43 GB 权重，也不会自动下载；模型载荷需单独部署到 `%LOCALAPPDATA%\LaborCaseAgent\models`。源码/GPU 环境已完成四个 provider 的真实验证；发布版 `rapidocr` 桌面 sidecar 只内置 CPU OCR，不包含其余重型依赖。后续发布还应记录上游 revision、许可证快照以及完整验证硬件/软件矩阵。
