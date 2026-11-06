# Windows v0.2 发布说明

## 安装包

- 文件：`dist/LaborCaseAgent.exe`
- 类型：Windows x64 NSIS 安装程序（不是 portable EXE）
- 版本：0.2.0
- 大小：507,218,500 字节
- SHA-256：`39fde2b6656eb298171f8fc45b3458d2dff5a7556f741c5000c2bc26489d389f`
- 签名：未签名，Windows SmartScreen 可能显示“未知发布者”

版本化文件 `dist/Labor Case Agent_0.2.0_x64-setup.exe` 与规范安装器字节一致。

2026-07-23 重建版包含线下立案预填材料包、模型管理后端和 RapidOCR 基础能力。安装器不内嵌约 14 GB 的可选模型权重，也不会静默下载模型。

## 安装与运行

仓库交付目录中可直接双击 `start-labor-case-agent.bat`。它只启动 Tauri 主程序，不会
绕过桌面应用单独启动 API 或 Node；因此正常关闭窗口时后台服务会一并退出。

运行安装程序后，默认安装到 `%LOCALAPPDATA%\Labor Case Agent`。案件数据库、
日志、设置和模型目录位于 `%LOCALAPPDATA%\LaborCaseAgent`，卸载应用前请按需
单独备份案件数据。

桌面外壳在本机启动 bundled Next.js 工作台和 FastAPI sidecar，分别监听
`127.0.0.1:3000` 与 `127.0.0.1:17831`。端口已被其他程序占用时应用不能正常
启动；请先关闭占用程序。服务不会监听局域网地址。

## 已验证范围

- 静默安装 `/S` 返回 0，安装版本为 0.2.0。
- 安装后的 bundled 工作台返回 HTTP 200，API health 为 `healthy` / `0.2.0`。
- 正常关闭窗口后两个端口均释放，安装目录下无 Node 或 API 孤儿进程。
- 安装目录含空格时，bundled Node 使用相对 `server.js` 入口；BAT 启动验证通过。
- RapidOCR 冻结 sidecar 对虚构聊天截图执行真实 CPU OCR，返回 11 个区域。
- Alembic 从 `0001_initial` 升级到 `0005_audio_fact_provenance`；设置持久化经重启验证。

## 模型边界

安装器内置 RapidOCR CPU 路径，不内嵌 Unlimited‑OCR、MOSS、BGE‑M3 或
Nemotron 的大型运行时/权重，也不会联网下载。独立的 `dist/models/` 载荷约
14.43 GiB，包含 147 个文件和 `checksums.sha256`，需要兼容的源码运行环境。

公开分发前应完成 Authenticode 签名、干净 Windows 10/11 虚拟机复验以及第三方
NOTICE/SBOM。更完整的安全与功能边界见 `security-v02.md`、
`known-limitations.md` 和 `v02-release.md`。
