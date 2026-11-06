# 本地部署

需要先区分 5090 路演环境与对外分发安装器。路演版运行
`start-roadshow-5090.bat`，个人安装版运行 `start-user-edition.bat` 或从系统快捷方式
启动。两个版本的数据目录、配置来源和模型策略见 `docs/editions.md`。

## Windows 快速启动

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e "apps/api[test,ocr]"
Set-Location apps\web
npm install
Set-Location ..\..
Copy-Item .env.example .env
.\.venv\Scripts\python -m alembic -c apps/api/alembic.ini upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir apps/api --port 8000
```

另开终端：

```powershell
Set-Location apps\web
npm run dev
```

访问 `http://localhost:3000`；API 文档为 `http://localhost:8000/docs`。

默认数据库：`data/labor_case_agent.db`。证据：`data/cases/{case_id}/original/`。不要把 `data/` 提交到 Git。
# Windows 桌面安装包（v0.2）

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-editions.ps1
```

生成的 `dist/LaborCaseAgent-UserSetup.exe` 是供用户下载的 x64 NSIS 安装程序。默认按当前用户
安装到 `%LOCALAPPDATA%\Labor Case Agent`；案件数据库、日志和模型目录位于
`%LOCALAPPDATA%\LaborCaseAgent`，与程序安装目录分开。API 和工作台只监听
`127.0.0.1:17831` 与 `127.0.0.1:3000`。

v0.2 发布包使用 `rapidocr` profile，可执行离线 CPU OCR；Unlimited‑OCR、
MOSS 与 embedding 的大型运行时和权重不嵌入 NSIS，仍保留人工录入兜底。
安装后可在“能力设置”中查看硬件与磁盘要求并自主下载可选能力包，或填写
OpenAI-compatible API 地址、模型名和密钥。Windows 密钥使用当前用户级
DPAPI 加密保存，不会写入普通 JSON 配置或打进 EXE。
准确发布范围与安全限制见 `docs/v02-release.md` 和 `docs/security-v02.md`。
