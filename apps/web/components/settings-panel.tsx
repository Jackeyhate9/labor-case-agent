"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Cloud,
  Cpu,
  Download,
  ExternalLink,
  HardDrive,
  LaptopMinimal,
  LockKeyhole,
  RefreshCw,
  ServerCog,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api, patch, post } from "@/lib/api";
import { Badge, Button, ErrorState } from "./ui";
import { DataManagementPanel } from "./data-management-panel";
import { ComplianceCenter } from "./compliance-center";

export type SystemSettings = {
  mode: "offline" | "online";
  llm_provider: string;
  ocr_provider: string;
  audio_provider: string;
  embedding_provider: string;
  redact_before_cloud: boolean;
  cloud_consent: boolean;
};
export type ProviderStatus = {
  name: string;
  kind?: string;
  status: string;
  model?: string;
  detail?: string;
};
type ModelPack = {
  id: string;
  name: string;
  capability: string;
  description: string;
  repo_id: string;
  revision: string;
  license: string;
  model_bytes: number;
  runtime_bytes: number;
  hardware: string;
  minimum_vram_gb: number;
  source_url: string;
  license_url: string;
  dependency_summary: string[];
  remote_code: boolean;
  recommended: boolean;
  installed: boolean;
  status: string;
};
type ModelManager = {
  onboarding_required: boolean;
  automatic_downloads: boolean;
  basic_mode: { ready: boolean; provider: string; description: string };
  model_root: string;
  runtime_root: string;
  system: {
    os: string;
    architecture: string;
    disk_free_bytes: number;
    nvidia_gpu: { name: string; memory_mib: number; driver: string } | null;
  };
  packs: ModelPack[];
};
type InstallJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  phase: string;
  message: string;
  downloaded_bytes: number;
  total_bytes: number;
  error?: string;
};
type LlmConfig = {
  provider: string;
  base_url: string;
  model: string;
  api_key_configured: boolean;
  storage: string;
  storage_available: boolean;
  returned: false;
};
type ConnectionResult = {
  ok: boolean;
  provider: string;
  base_url: string;
  model: string;
  latency_ms: number;
  message: string;
};
type AppProfile = {
  edition: "distribution" | "roadshow";
  configuration_mode: "user" | "environment";
  locked: boolean;
  providers?: Record<string, unknown>;
  assets?: Record<string, unknown>;
  model_root?: {
    path: string;
    source: string;
    registration_allowed: boolean;
  };
};

export const defaultSettings: SystemSettings = {
  mode: "offline",
  llm_provider: "disabled",
  ocr_provider: "auto",
  audio_provider: "disabled",
  embedding_provider: "disabled",
  redact_before_cloud: true,
  cloud_consent: false,
};
export function normalizeSettings(
  value:
    | (Partial<SystemSettings> & {
        offline_mode?: boolean;
      })
    | undefined,
): SystemSettings {
  if (!value) return defaultSettings;
  const mode =
    typeof value.offline_mode === "boolean"
      ? value.offline_mode
        ? "offline"
        : "online"
      : value.mode;
  return { ...defaultSettings, ...value, ...(mode ? { mode } : {}) };
}
export function normalizeProviders(value: unknown): ProviderStatus[] {
  if (Array.isArray(value)) return value as ProviderStatus[];
  if (!value || typeof value !== "object") return [];
  return Object.entries(value as Record<string, unknown>).flatMap(
    ([kind, item]) => {
      if (Array.isArray(item))
        return item.map((entry) => ({ kind, ...(entry as ProviderStatus) }));
      if (item && typeof item === "object") {
        const data = item as Record<string, unknown>;
        return [
          {
            name: String(data.name ?? data.provider ?? kind),
            kind,
            status: String(
              data.status ?? (data.available ? "available" : "unavailable"),
            ),
            model: data.model ? String(data.model) : undefined,
            detail: data.detail ? String(data.detail) : undefined,
          },
        ];
      }
      return [];
    },
  );
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 GB";
  return `${(bytes / 1024 ** 3).toFixed(bytes >= 10 * 1024 ** 3 ? 0 : 1)} GB`;
}

function hardwareLabel(pack: ModelPack) {
  if (pack.hardware === "nvidia_gpu_required")
    return `需 NVIDIA 显卡（显存至少 ${pack.minimum_vram_gb} GB）`;
  if (pack.hardware === "nvidia_gpu_recommended")
    return `建议 NVIDIA 显卡（显存 ${pack.minimum_vram_gb} GB 以上）`;
  return "支持 CPU，使用 NVIDIA 显卡会更快";
}

function ModelPackRow({
  pack,
  refresh,
}: {
  pack: ModelPack;
  refresh: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [licenseAccepted, setLicenseAccepted] = useState(false);
  const [downloadAccepted, setDownloadAccepted] = useState(false);
  const [jobId, setJobId] = useState<string>();
  const install = useMutation({
    mutationFn: () =>
      post(`/api/system/models/${pack.id}/install`, {
        accept_license: licenseAccepted,
        accept_download: downloadAccepted,
      }) as Promise<InstallJob>,
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useQuery({
    queryKey: ["model-job", jobId],
    queryFn: () => api<InstallJob>(`/api/system/model-jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["completed", "failed", "cancelled"].includes(status)
        ? false
        : 1000;
    },
  });
  useEffect(() => {
    if (job.data?.status === "completed") refresh();
  }, [job.data?.status, refresh]);
  const total = pack.model_bytes + pack.runtime_bytes;
  const progress =
    job.data?.total_bytes && job.data.total_bytes > 0
      ? Math.min(100, (job.data.downloaded_bytes / job.data.total_bytes) * 100)
      : 0;

  return (
    <article className="model-pack">
      <div className="model-pack-summary">
        <div className="model-pack-icon">
          {pack.installed ? <CheckCircle2 /> : <Cpu />}
        </div>
        <div>
          <div className="model-pack-title">
            <h3>{pack.name}</h3>
            {pack.recommended && <Badge status="warning">推荐</Badge>}
            {pack.installed && <Badge status="passed">已安装</Badge>}
          </div>
          <p>{pack.description}</p>
          <div className="model-pack-meta">
            <span>{formatBytes(total)}（模型与运行环境）</span>
            <span>{hardwareLabel(pack)}</span>
            <span>{pack.license}</span>
          </div>
        </div>
        <div className="model-pack-actions">
          {!pack.installed && (
            <Button
              variant={expanded ? "quiet" : "secondary"}
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
            >
              <Download size={15} />
              {expanded ? "收起" : `安装${pack.name}`}
            </Button>
          )}
        </div>
      </div>
      {expanded && !pack.installed && (
        <div className="model-pack-install">
          <p>
            安装程序将下载固定版本的模型文件与独立运行环境，不会修改系统
            Python。下载中断后可重新安装并续传。
          </p>
          <div className="model-pack-links">
            <a href={pack.source_url} target="_blank" rel="noreferrer">
              查看模型来源 <ExternalLink size={13} />
            </a>
            <a href={pack.license_url} target="_blank" rel="noreferrer">
              查看许可证 <ExternalLink size={13} />
            </a>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={licenseAccepted}
              onChange={(event) => setLicenseAccepted(event.target.checked)}
            />
            <span>我已查看并同意 {pack.license} 模型许可证</span>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={downloadAccepted}
              onChange={(event) => setDownloadAccepted(event.target.checked)}
            />
            <span>
              我同意下载约 {formatBytes(total)} 的模型与依赖，并了解其硬件要求
            </span>
          </label>
          {job.data && (
            <div className="install-progress" aria-live="polite">
              <div>
                <strong>{job.data.message}</strong>
                <span>{Math.round(progress)}%</span>
              </div>
              <progress value={progress} max={100} />
              {job.data.error && <p className="field-error">{job.data.error}</p>}
            </div>
          )}
          {install.isError && (
            <p className="field-error">{(install.error as Error).message}</p>
          )}
          <Button
            onClick={() => install.mutate()}
            busy={
              install.isPending ||
              job.data?.status === "queued" ||
              job.data?.status === "running"
            }
            disabled={!licenseAccepted || !downloadAccepted}
          >
            确认并开始下载
          </Button>
        </div>
      )}
    </article>
  );
}

function LocalCapabilityManager() {
  const client = useQueryClient();
  const manager = useQuery({
    queryKey: ["model-manager"],
    queryFn: () => api<ModelManager>("/api/system/model-manager"),
  });
  const profile = useQuery({
    queryKey: ["app-profile"],
    queryFn: () => api<AppProfile>("/api/system/app-profile"),
  });
  const [existingRoot, setExistingRoot] = useState("");
  const registerRoot = useMutation({
    mutationFn: () =>
      post("/api/system/model-manager/register-root", { path: existingRoot }),
    onSuccess: async () => {
      setExistingRoot("");
      await Promise.all([
        manager.refetch(),
        client.invalidateQueries({ queryKey: ["app-profile"] }),
      ]);
    },
  });
  const acknowledge = useMutation({
    mutationFn: () =>
      post("/api/system/model-manager/onboarding", { choice: "basic" }),
    onSuccess: () => manager.refetch(),
  });
  if (manager.isError)
    return (
      <ErrorState
        message={(manager.error as Error).message}
        retry={() => manager.refetch()}
      />
    );
  if (!manager.data)
    return <p className="form-note">正在检查本机模型与运行环境…</p>;
  const value = manager.data;
  if (
    !value.basic_mode ||
    !value.system ||
    !Array.isArray(value.packs)
  )
    return (
      <p className="form-note">
        当前服务端版本尚未提供本地模型管理；基础整理功能不受影响。
      </p>
    );
  return (
    <section className="capability-section" aria-labelledby="local-capabilities">
      <div className="capability-heading">
        <div>
          <p className="section-kicker">本机能力</p>
          <h2 id="local-capabilities">按需安装，不把大模型塞进 EXE</h2>
          <p>
            基础功能开箱可用。只有你主动确认后，程序才会下载额外模型和运行环境。
          </p>
        </div>
        <Badge status="user_confirmed">不会自动下载</Badge>
      </div>
      <div className="basic-mode-line">
        <CheckCircle2 />
        <div>
          <strong>基础模式已可用</strong>
          <p>{value.basic_mode.description}</p>
        </div>
        {value.onboarding_required && (
          <Button
            variant="secondary"
            busy={acknowledge.isPending}
            onClick={() => acknowledge.mutate()}
          >
            先使用基础模式
          </Button>
        )}
      </div>
      <div className="machine-summary">
        <span>
          可用磁盘 <strong>{formatBytes(value.system.disk_free_bytes)}</strong>
        </span>
        <span>
          显卡{" "}
          <strong>
            {value.system.nvidia_gpu
              ? `${value.system.nvidia_gpu.name} · ${Math.round(value.system.nvidia_gpu.memory_mib / 1024)} GB`
              : "未检测到 NVIDIA GPU"}
          </strong>
        </span>
        <span title={value.model_root}>
          安装位置 <strong>{value.model_root}</strong>
        </span>
      </div>
      {profile.data?.model_root?.registration_allowed ? (
        <div className="model-root-register">
          <div>
            <strong>已经下载过模型？直接登记现有目录</strong>
            <p>只保存本机路径，不复制文件，也不会重新下载已识别的模型。</p>
          </div>
          <input
            value={existingRoot}
            onChange={(event) => setExistingRoot(event.target.value)}
            placeholder={"例如 D:\\AI\\models"}
            aria-label="已有模型根目录"
          />
          <Button
            variant="secondary"
            busy={registerRoot.isPending}
            disabled={!existingRoot.trim()}
            onClick={() => registerRoot.mutate()}
          >
            扫描并登记
          </Button>
          {registerRoot.isError && (
            <p className="field-error">
              {(registerRoot.error as Error).message}
            </p>
          )}
        </div>
      ) : profile.data?.edition === "roadshow" ? (
        <p className="environment-managed-note">
          路演版模型目录由启动脚本管理。这里仅显示检测结果，不复制或改写现有模型。
        </p>
      ) : null}
      <div className="model-pack-list">
        {value.packs.map((pack) => (
          <ModelPackRow
            key={pack.id}
            pack={pack}
            refresh={() => void manager.refetch()}
          />
        ))}
      </div>
    </section>
  );
}

function CloudApiConfig({
  provider,
  locked = false,
}: {
  provider: string;
  locked?: boolean;
}) {
  const isOllama = provider === "ollama";
  const config = useQuery({
    queryKey: ["llm-config"],
    queryFn: () => api<LlmConfig>("/api/system/llm-config"),
  });
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  useEffect(() => {
    if (config.data && !Array.isArray(config.data)) {
      setBaseUrl(
        config.data.base_url || (isOllama ? "http://127.0.0.1:11434/v1" : ""),
      );
      setModel(config.data.model || (isOllama ? "llama3.2:latest" : ""));
    }
  }, [config.data, isOllama]);
  const save = useMutation({
    mutationFn: () =>
      patch("/api/system/llm-config", {
        base_url: baseUrl,
        model,
        ...(apiKey ? { api_key: apiKey } : {}),
      }),
    onSuccess: () => {
      setApiKey("");
      void config.refetch();
    },
  });
  const test = useMutation({
    mutationFn: () =>
      post("/api/system/llm-config/test", {
        base_url: baseUrl,
        model,
        ...(apiKey ? { api_key: apiKey } : {}),
      }) as Promise<ConnectionResult>,
  });
  const value =
    config.data && !Array.isArray(config.data) ? config.data : undefined;
  return (
    <section className="cloud-api-section" aria-labelledby="cloud-api-heading">
      <div className="capability-heading">
        <div>
          <p className="section-kicker">
            {isOllama ? "本机模型服务" : "外接 API 服务"}
          </p>
          <h2 id="cloud-api-heading">
            {isOllama ? "连接你的 Ollama 模型" : "使用你自己的模型 API"}
          </h2>
          <p>
            {isOllama
              ? "只访问本机回环地址，不需要 API 密钥，也不会把案件材料发送到互联网。"
              : "支持 OpenAI 兼容地址。密钥只写入 Windows 当前用户加密存储，页面与日志都不会回显。"}
          </p>
        </div>
        <Badge
          status={
            isOllama
              ? "user_confirmed"
              : value?.api_key_configured
                ? "passed"
                : "unreviewed"
          }
        >
          {isOllama
            ? "本机连接"
            : value?.api_key_configured
              ? "密钥已安全保存"
              : "尚未保存密钥"}
        </Badge>
      </div>
      {config.isError && (
        <ErrorState
          message={(config.error as Error).message}
          retry={() => config.refetch()}
        />
      )}
      <div className="api-config-grid">
        <label>
          服务类型
          <input
            value={provider}
            readOnly
            aria-label="API 服务类型"
            title="在下方能力路由中切换服务类型"
          />
        </label>
        <label>
          API 地址
          <input
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            readOnly={locked}
            placeholder={
              isOllama
                ? "http://127.0.0.1:11434/v1"
                : "https://api.example.com/v1"
            }
            aria-label="API 地址"
            autoComplete="url"
          />
        </label>
        <label>
          模型名称
          <input
            value={model}
            onChange={(event) => setModel(event.target.value)}
            readOnly={locked}
            placeholder={isOllama ? "例如 llama3.2:latest" : "例如 qwen-plus"}
            aria-label="模型名称"
            autoComplete="off"
          />
        </label>
        {!isOllama && (
          <label>
            API 密钥
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              disabled={locked}
              placeholder={
                value?.api_key_configured
                  ? "已保存；留空表示继续使用"
                  : "输入服务商提供的 API Key"
              }
              aria-label="API 密钥"
              autoComplete="new-password"
            />
          </label>
        )}
      </div>
      <div className="credential-note">
        {isOllama ? <HardDrive size={17} /> : <LockKeyhole size={17} />}
        <div>
          <strong>
            {isOllama
              ? "Ollama 模型仍由你自己管理"
              : value?.storage_available
                ? "使用 Windows DPAPI 用户级加密"
                : "当前系统不支持在程序内安全保存密钥"}
          </strong>
          <p>
            {isOllama
              ? "程序只记录服务地址和模型名称，不复制 Ollama 模型。测试连接时仅读取本机模型列表。"
              : "密钥不会包含在导出包或 EXE 中。测试连接时仅访问该地址的模型列表，不发送任何案件材料。"}
          </p>
        </div>
      </div>
      {(save.isError || test.isError) && (
        <p className="field-error">
          {((save.error || test.error) as Error).message}
        </p>
      )}
      {test.data && (
        <p
          className={`connection-result ${test.data.ok ? "success" : "failed"}`}
          aria-live="polite"
        >
          {test.data.message}
          {test.data.ok ? ` · ${test.data.latency_ms} ms` : ""}
        </p>
      )}
      <div className="api-config-actions">
        <Button
          variant="secondary"
          busy={test.isPending}
          disabled={!baseUrl || !model}
          onClick={() => test.mutate()}
        >
          测试连接
        </Button>
        <Button
          busy={save.isPending}
          disabled={
            !baseUrl ||
            !model ||
            locked ||
            (!isOllama && value?.storage_available === false)
          }
          onClick={() => save.mutate()}
        >
          {isOllama ? "保存 Ollama 配置" : "保存 API 配置"}
        </Button>
      </div>
    </section>
  );
}

function EditionOverview() {
  const profile = useQuery({
    queryKey: ["app-profile"],
    queryFn: () => api<AppProfile>("/api/system/app-profile"),
  });
  if (!profile.data) return null;
  const roadshow = profile.data.edition === "roadshow";
  return (
    <section
      className={`edition-overview ${roadshow ? "roadshow" : "distribution"}`}
      aria-labelledby="edition-heading"
    >
      <div className="edition-mark" aria-hidden="true">
        {roadshow ? <LaptopMinimal /> : <ShieldCheck />}
      </div>
      <div className="edition-copy">
        <div className="edition-title">
          <h2 id="edition-heading">
            {roadshow ? "5090 本地路演版" : "个人安装版"}
          </h2>
          <Badge status={roadshow ? "user_confirmed" : "passed"}>
            {roadshow ? "复用本机模型" : "轻量安装器"}
          </Badge>
        </div>
        <p>
          {roadshow
            ? "当前由启动环境接管能力配置，直接使用本机 Ollama、显卡和已下载模型，不重复下载。"
            : "安装器不携带大模型。基础 OCR 开箱可用，你可以连接自己的 Ollama 或 API，再按需下载语义检索、录音转写等能力。"}
        </p>
      </div>
      <dl className="edition-facts">
        <div>
          <dt>配置来源</dt>
          <dd>{roadshow ? "路演启动脚本" : "当前用户设置"}</dd>
        </div>
        <div>
          <dt>模型位置</dt>
          <dd title={profile.data.model_root?.path}>
            {roadshow ? "现有本地集合" : "用户选择后下载"}
          </dd>
        </div>
      </dl>
    </section>
  );
}

export function SettingsPanel() {
  const client = useQueryClient();
  const appProfile = useQuery({
    queryKey: ["app-profile"],
    queryFn: () => api<AppProfile>("/api/system/app-profile"),
  });
  const profileLocked = appProfile.data?.locked === true;
  const settings = useQuery({
    queryKey: ["system-settings"],
    queryFn: () =>
      api<Partial<SystemSettings> & { offline_mode?: boolean }>(
        "/api/system/settings",
      ),
  });
  const providers = useQuery({
    queryKey: ["system-providers"],
    queryFn: () => api<unknown>("/api/system/providers"),
  });
  const [form, setForm] = useState<SystemSettings>(defaultSettings);
  useEffect(() => {
    if (settings.data) setForm(normalizeSettings(settings.data));
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () =>
      patch("/api/system/settings", {
        offline_mode: form.mode === "offline",
        llm_provider: form.llm_provider,
        ocr_provider: form.ocr_provider,
        audio_provider: form.audio_provider,
        embedding_provider: form.embedding_provider,
      }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["system-settings"] }),
        client.invalidateQueries({ queryKey: ["system-providers"] }),
      ]);
    },
  });
  const statuses = normalizeProviders(providers.data);
  const knownLlmProviders = [
    "disabled",
    "ollama",
    "openai-compatible",
    "deepseek-compatible",
    "qwen-compatible",
  ];
  const isCloudProvider = [
    "openai-compatible",
    "deepseek-compatible",
    "qwen-compatible",
  ].includes(form.llm_provider);
  return (
    <div className="settings-stack">
      <EditionOverview />
      <section className="mode-switch" aria-label="运行模式">
        <button
          type="button"
          disabled={profileLocked}
          className={form.mode === "offline" ? "active" : ""}
          onClick={() =>
            setForm({ ...form, mode: "offline", cloud_consent: false })
          }
        >
          <HardDrive />
          <span>
            <strong>离线整理</strong>
            <small>证据不发送给云端，使用本地 OCR 与模型</small>
          </span>
          <Badge status={form.mode === "offline" ? "user_confirmed" : undefined}>
            {form.mode === "offline" ? "当前模式" : "可选择"}
          </Badge>
        </button>
        <button
          type="button"
          disabled={profileLocked}
          className={form.mode === "online" ? "active" : ""}
          onClick={() => setForm({ ...form, mode: "online" })}
        >
          <Cloud />
          <span>
            <strong>在线增强</strong>
            <small>仅在明确同意后向配置的云服务发送内容</small>
          </span>
          <Badge status={form.mode === "online" ? "unreviewed" : undefined}>
            {form.mode === "online" ? "需确认范围" : "可选择"}
          </Badge>
        </button>
      </section>

      {settings.isError && (
        <ErrorState
          message={`${(settings.error as Error).message}。后端尚未开放设置接口时，当前选择不会被伪装为已保存。`}
          retry={() => settings.refetch()}
        />
      )}

      <section className="settings-sheet">
        <header>
          <div>
            <p className="section-kicker">能力路由</p>
            <h2>选择实际使用的处理能力</h2>
          </div>
          <ServerCog />
        </header>
        {profileLocked && (
          <p className="environment-managed-note">
            当前是路演环境，能力路由由启动脚本锁定。你仍可测试连接和查看实际状态；
            如需更换模型，请修改路演启动配置后重新启动。
          </p>
        )}
        <div className="field-grid four">
          <label>
            语言模型
            <select
              aria-label="语言模型"
              disabled={profileLocked}
              value={form.llm_provider}
              onChange={(event) =>
                setForm({ ...form, llm_provider: event.target.value })
              }
            >
              {!knownLlmProviders.includes(form.llm_provider) && (
                <option value={form.llm_provider}>{form.llm_provider}</option>
              )}
              <option value="disabled">不使用语言模型</option>
              <option value="ollama">Ollama（本机）</option>
              <option value="openai-compatible">OpenAI 兼容 API</option>
              <option value="deepseek-compatible">DeepSeek 兼容 API</option>
              <option value="qwen-compatible">通义千问兼容 API</option>
            </select>
          </label>
          <label>
            OCR 引擎
            <select
              aria-label="OCR 引擎"
              disabled={profileLocked}
              value={form.ocr_provider}
              onChange={(event) =>
                setForm({ ...form, ocr_provider: event.target.value })
              }
            >
              <option value="auto">自动选择</option>
              <option value="rapidocr">RapidOCR（本机基础）</option>
              <option value="ollama-ocr">Ollama OCR（使用本机视觉模型）</option>
              <option value="unlimited-ocr">智能长文档 OCR（需安装）</option>
              <option value="disabled">关闭 OCR</option>
            </select>
          </label>
          <label>
            录音转写
            <select
              aria-label="录音转写"
              disabled={profileLocked}
              value={form.audio_provider}
              onChange={(event) =>
                setForm({ ...form, audio_provider: event.target.value })
              }
            >
              <option value="disabled">不使用录音转写</option>
              <option value="moss-transcribe-diarize">
                MOSS 转写与说话人区分（需安装）
              </option>
            </select>
          </label>
          <label>
            向量模型
            <select
              aria-label="向量模型"
              disabled={profileLocked}
              value={form.embedding_provider}
              onChange={(event) =>
                setForm({ ...form, embedding_provider: event.target.value })
              }
            >
              <option value="disabled">不使用语义检索</option>
              <option value="bge-m3">BGE-M3（需安装）</option>
              <option value="nemotron-3-embed-1b">Nemotron（需安装）</option>
            </select>
          </label>
        </div>
        <label className="check">
          <input
            type="checkbox"
            disabled={profileLocked}
            checked={form.redact_before_cloud}
            onChange={(event) =>
              setForm({ ...form, redact_before_cloud: event.target.checked })
            }
          />
          <span>
            向云端发送前，对身份证号、手机号等敏感信息自动脱敏
          </span>
        </label>
        {form.mode === "online" && (
          <label className="cloud-consent">
            <input
              type="checkbox"
              disabled={profileLocked}
              checked={form.cloud_consent}
              onChange={(event) =>
                setForm({ ...form, cloud_consent: event.target.checked })
              }
            />
            <LockKeyhole />
            <span>
              <strong>我已了解在线发送范围</strong>
              <small>当前 V1 只测试连接，不会自动发送案件材料；未来启用业务调用时需另行逐次确认。</small>
            </span>
          </label>
        )}
        <div className="settings-actions">
          <span>
            {save.isSuccess
              ? "设置已由服务端保存"
              : "修改后需要保存才会生效"}
          </span>
          <Button
            onClick={() => save.mutate()}
            busy={save.isPending}
            disabled={
              profileLocked ||
              (form.mode === "online" && !form.cloud_consent)
            }
          >
            保存能力设置
          </Button>
        </div>
        {save.isError && (
          <p className="field-error">{(save.error as Error).message}</p>
        )}
      </section>

      {form.llm_provider === "ollama" ||
      (form.mode === "online" && isCloudProvider) ? (
        <CloudApiConfig
          provider={form.llm_provider}
          locked={profileLocked}
        />
      ) : null}

      <LocalCapabilityManager />

      <DataManagementPanel />

      <ComplianceCenter />

      <section className="provider-ledger">
        <div className="action-bar">
          <div>
            <h2>实际运行状态</h2>
            <p>这里显示服务端探测结果，不根据表单选择推测可用性。</p>
          </div>
          <Button
            variant="secondary"
            busy={providers.isFetching}
            onClick={() => providers.refetch()}
          >
            <RefreshCw size={15} />
            刷新状态
          </Button>
        </div>
        {providers.isError ? (
          <ErrorState
            message={(providers.error as Error).message}
            retry={() => providers.refetch()}
          />
        ) : statuses.length ? (
          statuses.map((provider) => (
            <article key={`${provider.kind}-${provider.name}`}>
              <span
                className={`provider-light ${provider.status}`}
                aria-hidden="true"
              />
              <div>
                <strong>{provider.name}</strong>
                <small>
                  {provider.kind ?? "provider"}
                  {provider.model ? ` · ${provider.model}` : ""}
                </small>
              </div>
              <Badge
                status={
                  provider.status === "available"
                    ? "passed"
                    : provider.status === "degraded"
                      ? "warning"
                      : "failed"
                }
              >
                {provider.status}
              </Badge>
              {provider.detail && <p>{provider.detail}</p>}
            </article>
          ))
        ) : (
          <p className="form-note">服务端尚未返回 Provider 探测项。</p>
        )}
      </section>
    </div>
  );
}
