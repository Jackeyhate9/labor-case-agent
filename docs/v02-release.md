# v0.2 Windows 桌面发布记录

## 交付架构

Tauri v2 提供 Windows 外壳；PyInstaller one-file sidecar 提供 FastAPI 与 RapidOCR；Next.js standalone 和 Node.js 运行时随 NSIS 安装。API 与工作台分别只监听 `127.0.0.1:17831` 和 `127.0.0.1:3000`，WebView2 使用离线安装模式。

`dist/LaborCaseAgent.exe` 是规范化的 **NSIS 安装程序**，不是 portable EXE。模型权重作为 `dist/models` 独立载荷，不嵌入安装器。

## 2026-07-27 实际验收

- `scripts/build-sidecar.ps1 -Profile rapidocr` 成功；冻结 sidecar 健康检查为 `healthy`、版本 `0.2.0`。
- 冻结 sidecar 将隔离的 Alembic `0001_initial` 数据库升级到 `0005_audio_fact_provenance`，并确认 `facts.source_audio_segment_id` 存在。早期无版本表但具有 v0.1 核心表的数据库会先安全 stamp；未知数据库会拒绝启动，不会删除。
- PATCH 系统设置写入 `%LOCALAPPDATA%\LaborCaseAgent\data\system-settings.json`，sidecar 重启后仍保持。
- 上传 `samples/demo-case/chat-01.png` 后，冻结 sidecar 返回 `ocr_engine=rapidocr`、11 个区域、无 warning。
- 最新 `apps/web` Next standalone 构建成功，动态案件路由已包含；`cargo check` 成功。
- x64 NSIS 构建成功；静默安装 `/S` 退出码为 0，注册版本 0.2.0，默认目录为 `%LOCALAPPDATA%\Labor Case Agent`。
- 安装后 bundled Node 工作台返回 HTTP 200，冻结 API 返回 `healthy`、版本 `0.2.0`，Tauri 主进程保持运行。正常关闭主窗口后端口 3000/17831 均释放，安装目录下没有残留 Node/API 进程。
- “能力设置”已接入四个可选本地能力包，显示磁盘、GPU、下载体积、许可证与安装进度；基础模式无需下载，所有额外下载均要求用户逐项确认。
- 用户可配置 OpenAI-compatible API 地址、模型名与密钥并测试连接；密钥仅以 Windows 当前用户级 DPAPI 密文保存，GET、错误和日志均不回显。

## 模型能力边界

Unlimited OCR（RTX 5090：40.3 秒、684 字符、11 区域框）、MOSS、BGE-M3 与 Nemotron Embed 已在源码/模型环境真实验证。RapidOCR 则已在冻结桌面 sidecar 真实验证。不要把源码/GPU 验证误报为 NSIS 对所有大型模型开箱即用。

`dist/models` 含四个模型、147 个文件、约 14.43 GiB，并附逐文件 checksums；NSIS 不自动下载或嵌入它们。分发时可只提供安装器，用户再在“能力设置”中自主选择所需能力包。

## 已知限制

- API 尚无随机会话令牌；同一用户的其他本机进程可请求回环 API。
- 安装包未代码签名，没有自动更新、SBOM 或完整第三方 NOTICE。
- 端口 17831/3000 固定；占用时不会自动选择备用端口。
- PyInstaller 报告一个未解析的可选 `tbb12.dll` 依赖，但本次 RapidOCR 样本推理成功。

## 重现

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-sidecar.ps1 -Profile rapidocr
powershell -ExecutionPolicy Bypass -File scripts/build-desktop.ps1 -SkipSidecar -SidecarProfile rapidocr
```

最终文件哈希和大小记录于 `dist/desktop-build-manifest.json`；公开发布前仍须在干净 Windows 10/11 虚拟机复验并完成签名。

2026-07-27 重建的 `dist/LaborCaseAgent.exe` 为 507,551,954 字节，SHA-256：`838774dfdb40457506cd2567883418a75908da6798daca1307ddace11aabc321`；未签名。安装路径含空格的 bundled Node 入口使用相对 `server.js`。重建包已完成静默安装、安装后侧车与工作台启动、健康检查、模型管理路由和安全 LLM 配置路由验证。
