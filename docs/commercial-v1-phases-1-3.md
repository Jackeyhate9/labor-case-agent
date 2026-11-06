# 商业化 V1：前三阶段交付说明

更新时间：2026-07-29

## 第一阶段：发布安全与供应链

- 桌面端每次启动生成随机会话令牌，API 仅接受正确的 `X-App-Session` 或同源
  HttpOnly / SameSite=Strict 会话 Cookie。
- API 与 Web 使用动态回环端口，避免固定端口冲突；桌面 CSP 仅允许本机回环访问。
- Web 生产依赖已升级并通过 `npm audit --audit-level=high`（0 漏洞）。
- `scripts/generate-sbom.ps1` 生成 Web、Python、Rust 三份 CycloneDX SBOM 和哈希索引。
- `scripts/sign-release.ps1` 使用 Windows Authenticode SHA-256 签名、可信时间戳并立即验签。
- `scripts/assert-commercial-release.ps1` 检查发行主体、支持邮箱、法律页面、安装包哈希和
  有效签名；任一条件缺失即拒绝商业发布。
- Windows CI 会在干净环境运行后端、前端、生产构建和桌面 Rust 检查；手动发行工作流
  负责导入证书、构建、SBOM、签名和上传制品。

正式构建前在 CI Variables 配置 `PUBLISHER_NAME`、`SUPPORT_EMAIL`，在 Secrets 配置
`WINDOWS_CERTIFICATE_BASE64`、`WINDOWS_CERTIFICATE_PASSWORD`。本机可执行：

```powershell
$env:PUBLISHER_NAME = "实际发行主体"
$env:SUPPORT_EMAIL = "support@example.com"
$env:SIGNING_CERT_THUMBPRINT = "证书指纹"
.\scripts\build-desktop.ps1 -CommercialRelease
```

## 第二阶段：数据安全

- 用户可创建 AES-256-GCM 加密的 `.lca-backup`；口令通过 PBKDF2-SHA256（60 万次）
  派生，API Key 不进入备份。
- 恢复前校验格式、路径、清单、逐文件 SHA-256、SQLite `quick_check` 和关键表。
- 恢复采用数据库、证据目录和非密钥设置的整体回滚；任一步失败均恢复操作前状态。
- 数据库迁移前自动创建 SQLite 快照并保留最近三份。
- 设置页支持备份下载、恢复、查看存储状态，以及输入固定确认短语后清除全部案件。
- 系统自检包含 SQLite 完整性检查。

备份口令无法找回；正式运维应定期做“新建测试案件 → 备份 → 独立数据目录恢复”的演练。

## 第三阶段：商业合规

- 首次启动必须逐项确认用户协议、敏感信息处理和 AI/自动化说明；接受记录按政策版本保存。
- 法律页面在未接受时也可阅读；政策版本变化后会要求重新确认。
- 能力设置中可查看接受时间并撤回同意；撤回后仍允许备份、恢复和清除数据。
- 页面明确本工具不构成法律意见，当前 V1 业务链路不会自动调用云端 LLM，也不会后台
  静默发送案件材料。
- 未配置发行主体和支持邮箱时，首次使用页显示内部验证警告，商业发布门禁同时拒绝放行。

协议文本是产品工程版本，正式公开销售前仍应由实际经营主体的律师结合经营模式、收费方式、
第三方服务和售后政策完成最终审定。

## 本轮验收结果

- 后端：132 项测试通过。
- 前端：28 项测试通过。
- Next.js 生产构建：通过。
- npm 高危审计：0 漏洞。
- Tauri/Rust `cargo check`：通过。
- PowerShell 脚本语法、Git whitespace 检查、GitHub Actions YAML 解析：通过。
- 商业发布负向门禁：当前未签名安装器被正确拒绝。
