"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  BriefcaseBusiness,
  Calculator,
  Check,
  CircleDashed,
  ClipboardCheck,
  Download,
  FileArchive,
  FileSearch,
  FileText,
  FolderOpen,
  Menu,
  Plus,
  RefreshCw,
  Scale,
  Settings,
  ShieldAlert,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { EvidenceChain } from "./evidence-chain";
import { EvidencePreview, PreviewData } from "./evidence-preview";
import { SettingsPanel } from "./settings-panel";
import { Badge, Button, Empty, ErrorState, StatusIcon } from "./ui";
import { api, CaseItem, Evidence, Fact, getCase, patch, post } from "@/lib/api";
const sections = [
  { key: "overview", label: "案件总览", icon: FolderOpen },
  { key: "evidence", label: "证据与 OCR", icon: FileSearch },
  { key: "facts", label: "事实确认", icon: ClipboardCheck },
  { key: "timeline", label: "时间线", icon: BookOpen },
  { key: "employment", label: "劳动关系", icon: BriefcaseBusiness },
  { key: "wages", label: "工资明细", icon: Calculator },
  { key: "claims", label: "仲裁请求", icon: Scale },
  { key: "gaps", label: "证据缺口", icon: CircleDashed },
  { key: "review", label: "证据审查", icon: ClipboardCheck },
  { key: "defense", label: "抗辩模拟", icon: ShieldAlert },
  { key: "documents", label: "文书", icon: FileText },
  { key: "export", label: "导出档案", icon: FileArchive },
  { key: "self-check", label: "系统自检", icon: Check },
  { key: "settings", label: "能力设置", icon: Settings },
];
const chainLevel: Record<string, string> = {
  overview: "raw",
  evidence: "raw",
  facts: "machine",
  timeline: "confirmed",
  employment: "confirmed",
  wages: "confirmed",
  claims: "confirmed",
  gaps: "confirmed",
  review: "confirmed",
  defense: "confirmed",
  documents: "draft",
  export: "draft",
  "self-check": "draft",
  settings: "raw",
};
export function CaseWorkspace({
  caseId,
  section,
}: {
  caseId: string;
  section: string;
}) {
  const [menu, setMenu] = useState(false);
  const current = sections.find((s) => s.key === section) ?? sections[0];
  const c = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
  });
  return (
    <div className="workspace">
      <aside className={`case-sidebar ${menu ? "open" : ""}`}>
        <Link href="/" className="sidebar-back">
          <ArrowLeft size={15} />
          全部案件
        </Link>
        <div className="case-identity">
          <span>卷宗编号</span>
          <code>{caseId.slice(0, 12)}</code>
          <strong>{c.data?.title ?? "载入案件…"}</strong>
          <Badge status={c.data?.status}>{c.data?.status ?? "整理中"}</Badge>
        </div>
        <nav>
          {sections.map((s) => (
            <Link
              key={s.key}
              href={`/cases/${caseId}/${s.key}`}
              className={s.key === current.key ? "active" : ""}
              onClick={() => setMenu(false)}
            >
              <s.icon size={17} />
              {s.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="case-content">
        <div className="mobile-casebar">
          <button onClick={() => setMenu(!menu)} aria-label="打开案件导航">
            <Menu />
          </button>
          <strong>{current.label}</strong>
        </div>
        <header className="case-page-head">
          <div>
            <p className="eyebrow">
              {current.key.toUpperCase()} · {caseId.slice(0, 8)}
            </p>
            <h1>{current.label}</h1>
          </div>
          <Badge status="user_confirmed">仅已确认事实进入正式文书</Badge>
        </header>
        <EvidenceChain active={chainLevel[current.key]} compact />
        {c.isError ? (
          <ErrorState
            message={(c.error as Error).message}
            retry={() => c.refetch()}
          />
        ) : (
          <Section caseId={caseId} section={current.key} caseData={c.data} />
        )}
      </main>
    </div>
  );
}
function Section({
  caseId,
  section,
  caseData,
}: {
  caseId: string;
  section: string;
  caseData?: CaseItem;
}) {
  switch (section) {
    case "evidence":
      return <EvidenceView caseId={caseId} />;
    case "facts":
      return <FactsView caseId={caseId} />;
    case "timeline":
      return <TimelineView caseId={caseId} />;
    case "employment":
      return <EmploymentView caseId={caseId} />;
    case "wages":
      return <WagesView caseId={caseId} />;
    case "claims":
      return <ClaimsView caseId={caseId} />;
    case "gaps":
      return <WorkflowView key="gaps" caseId={caseId} kind="gaps" />;
    case "review":
      return <WorkflowView key="review" caseId={caseId} kind="review" />;
    case "defense":
      return <WorkflowView key="defense" caseId={caseId} kind="defense" />;
    case "documents":
      return <DocumentsView caseId={caseId} />;
    case "export":
      return <ExportView caseId={caseId} />;
    case "self-check":
      return <SelfCheck />;
    case "settings":
      return <SettingsPanel />;
    default:
      return <Overview caseId={caseId} data={caseData} />;
  }
}
function Overview({ caseId, data }: { caseId: string; data?: CaseItem }) {
  const facts = useQuery({
    queryKey: ["facts", caseId],
    queryFn: () => api<Fact[]>(`/api/cases/${caseId}/facts`),
  });
  const ev = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => api<Evidence[]>(`/api/cases/${caseId}/evidence`),
  });
  const graph = useQuery({
    queryKey: ["evidence-graph", caseId],
    queryFn: () =>
      api<{ node_count: number; edge_count: number }>(`/api/cases/${caseId}/graph`),
  });
  const counts = {
    confirmed:
      facts.data?.filter((x) => x.review_status === "user_confirmed").length ??
      0,
    pending:
      facts.data?.filter((x) =>
        ["unreviewed", "machine_extracted"].includes(x.review_status),
      ).length ?? 0,
    conflicted:
      facts.data?.filter((x) => x.review_status === "conflicted").length ?? 0,
  };
  return (
    <div className="content-stack">
      <section className="dossier-summary">
        <div>
          <span>案情摘要</span>
          <p>
            {data?.summary || "尚未形成案件摘要。请先补充基本情况并上传证据。"}
          </p>
        </div>
        <dl>
          <div>
            <dt>争议类型</dt>
            <dd>{data?.case_type || "劳动争议"}</dd>
          </div>
          <div>
            <dt>管辖地区</dt>
            <dd>{data?.jurisdiction_region || "待确认"}</dd>
          </div>
          <div>
            <dt>案件状态</dt>
            <dd>{data?.status || "整理中"}</dd>
          </div>
        </dl>
      </section>
      <div className="metric-ledger">
        <div>
          <strong>{ev.data?.length ?? 0}</strong>
          <span>原始证据</span>
        </div>
        <div>
          <strong>{counts.confirmed}</strong>
          <span>已确认事实</span>
        </div>
        <div>
          <strong>{counts.pending}</strong>
          <span>待确认事实</span>
        </div>
        <div className={counts.conflicted ? "warn" : ""}>
          <strong>{counts.conflicted}</strong>
          <span>冲突事实</span>
        </div>
        <div>
          <strong>
            {graph.data?.node_count ?? 0}/{graph.data?.edge_count ?? 0}
          </strong>
          <span>图谱节点 / 关系</span>
        </div>
      </div>
      <section className="next-action">
        <span className="amber-rule" />
        <div>
          <p className="eyebrow">下一步建议</p>
          <h2>
            {(ev.data?.length ?? 0) === 0
              ? "先上传手边的材料"
              : "核对机器提取的候选事实"}
          </h2>
          <p>
            {(ev.data?.length ?? 0) === 0
              ? "聊天截图、工资流水、社保记录都可以单独或批量上传。"
              : "只有你确认的事实，才会进入时间线、金额计算与正式文书。"}
          </p>
        </div>
        <Link
          className="button button-primary"
          href={`/cases/${caseId}/${(ev.data?.length ?? 0) === 0 ? "evidence" : "facts"}`}
        >
          继续整理
        </Link>
      </section>
      <section>
        <div className="section-heading">
          <h2>主要风险提示</h2>
        </div>
        <div className="notice warning">
          <AlertTriangle size={18} />
          <div>
            <strong>管辖地与仲裁时效尚待复核</strong>
            <p>系统无法替代对法律适用、时效和证据原件的专业判断。</p>
          </div>
        </div>
      </section>
    </div>
  );
}
function EvidenceView({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<Evidence>();
  const q = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => api<Evidence[]>(`/api/cases/${caseId}/evidence`),
  });
  const upload = useMutation({
    mutationFn: async (files: FileList) => {
      const fd = new FormData();
      Array.from(files).forEach((f) => fd.append("files", f));
      try {
        return await api(`/api/cases/${caseId}/evidence`, {
          method: "POST",
          body: fd,
        });
      } catch {
        const outputs = [];
        for (const f of Array.from(files)) {
          const one = new FormData();
          one.append("file", f);
          outputs.push(
            await api(`/api/cases/${caseId}/evidence`, {
              method: "POST",
              body: one,
            }),
          );
        }
        return outputs;
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evidence", caseId] }),
  });
  const process = useMutation({
    mutationFn: (id: string) =>
      preview.data?.kind === "audio"
        ? post(`/api/evidence/${id}/audio/transcribe`)
        : post(`/api/evidence/${id}/process`),
    onSuccess: (result) => {
      if (result?.evidence) setSelected(result.evidence);
      qc.invalidateQueries({ queryKey: ["evidence", caseId] });
      qc.invalidateQueries({ queryKey: ["ocr", selected?.id] });
      qc.invalidateQueries({ queryKey: ["audio-segments", selected?.id] });
    },
  });
  const ocr = useQuery({
    queryKey: ["ocr", selected?.id],
    queryFn: () => api<any>(`/api/evidence/${selected!.id}/ocr`),
    enabled: !!selected,
  });
  const preview = useQuery({
    queryKey: ["evidence-preview", selected?.id],
    queryFn: () => api<PreviewData>(`/api/evidence/${selected!.id}/preview/data`),
    enabled: !!selected,
  });
  const segments = useQuery({
    queryKey: ["audio-segments", selected?.id],
    queryFn: () => api<any[]>(`/api/evidence/${selected!.id}/audio/segments`),
    enabled: !!selected && preview.data?.kind === "audio",
  });
  return (
    <div className="split-view">
      <section>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.txt,.csv,.xlsx,.mp3,.wav,.m4a,.mp4"
          onChange={(e) => e.target.files && upload.mutate(e.target.files)}
        />
        <button
          className="upload-zone"
          onClick={() => input.current?.click()}
          disabled={upload.isPending}
        >
          <Upload />
          <strong>
            {upload.isPending ? "正在上传…" : "选择或拖放证据文件"}
          </strong>
          <span>图片、PDF、DOCX、TXT、CSV、XLSX、音频 · 支持批量</span>
        </button>
        {upload.isError && (
          <p className="field-error">{(upload.error as Error).message}</p>
        )}
        <div className="evidence-list">
          {q.data?.map((e) => (
            <button
              key={e.id}
              className={selected?.id === e.id ? "selected" : ""}
              onClick={() => setSelected(e)}
            >
              <span className="evidence-no">
                {e.evidence_number || "待编号"}
              </span>
              <span>
                <strong>{e.original_filename}</strong>
                <small>
                  {e.document_type || "材料"} · OCR {e.ocr_status || "待处理"}
                </small>
              </span>
              <Badge status={e.processing_status}>
                {e.processing_status || "已上传"}
              </Badge>
            </button>
          ))}
        </div>
        {!q.isLoading && !q.data?.length && (
          <Empty
            title="证据库是空的"
            body="上传原始文件后，系统会保留文件哈希、页码、OCR 原文和处理状态。"
          />
        )}
      </section>
      <aside className="inspector">
        {selected ? (
          <>
            <div className="inspector-head">
              <div>
                <span>{selected.evidence_number}</span>
                <h2>{selected.original_filename}</h2>
              </div>
              <Button
                onClick={() => process.mutate(selected.id)}
                busy={process.isPending}
              >
                <RefreshCw size={15} />
                运行解析
              </Button>
            </div>
            <div className="source-meta">
              <span>
                处理状态{" "}
                <Badge status={selected.processing_status}>
                  {selected.processing_status || "已上传"}
                </Badge>
              </span>
              <span>
                OCR 状态{" "}
                <Badge status={selected.ocr_status}>
                  {selected.ocr_status || "待运行"}
                </Badge>
              </span>
            </div>
            <h3>原件与提取定位</h3>
            {preview.isLoading ? (
              <p className="form-note">正在建立安全预览…</p>
            ) : preview.isError ? (
              <ErrorState message={(preview.error as Error).message} retry={() => preview.refetch()} />
            ) : preview.data ? (
              <EvidencePreview
                preview={preview.data}
                pages={ocr.data?.pages ?? []}
                segments={segments.data ?? []}
              />
            ) : null}
            <p className="form-note">
              OCR 原文始终保留；用户修正不会覆盖原始识别结果。
            </p>
          </>
        ) : (
          <Empty
            title="选择一份证据查看详情"
            body="可查看处理状态、OCR 原文与后续提取结果。"
          />
        )}
      </aside>
    </div>
  );
}
function FactsView({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Fact>();
  const [value, setValue] = useState("");
  const q = useQuery({
    queryKey: ["facts", caseId],
    queryFn: () => api<Fact[]>(`/api/cases/${caseId}/facts`),
  });
  const act = useMutation({
    mutationFn: ({
      id,
      action,
      value,
    }: {
      id: string;
      action: string;
      value?: string;
    }) => {
      if (action !== "edit") return post(`/api/facts/${id}/${action}`);
      return patch(`/api/facts/${id}`, { user_corrected_value: value }).then(
        () => post(`/api/facts/${id}/confirm`),
      );
    },
    onSuccess: () => {
      setEditing(undefined);
      qc.invalidateQueries({ queryKey: ["facts", caseId] });
    },
  });
  return (
    <div className="content-stack">
      <div className="filter-strip">
        <span>候选事实 {q.data?.length ?? 0}</span>
        <span>
          <i className="dot amber" />
          机器提取，待确认
        </span>
        <span>
          <i className="dot green" />
          用户已确认
        </span>
        <span>
          <i className="dot red" />
          冲突或拒绝
        </span>
      </div>
      {q.isError && <ErrorState message={(q.error as Error).message} />}
      <div className="fact-list">
        {q.data?.map((f) => (
          <article key={f.id} className={`fact-row ${f.review_status}`}>
            <div className="fact-state">
              <Badge status={f.review_status}>
                {statusText(f.review_status)}
              </Badge>
              <small>{f.fact_type || "候选事实"}</small>
            </div>
            <div className="fact-body">
              <p>
                {f.user_corrected_value ||
                  f.normalized_value ||
                  f.object_value ||
                  f.predicate ||
                  "待核对内容"}
              </p>
              <blockquote>“{f.source_quote || "原文摘录未提供"}”</blockquote>
              <div className="provenance">
                <code>{f.source_evidence_id || "来源待关联"}</code>
                <span>
                  {f.source_page ? `第 ${f.source_page} 页` : "页码待确认"}
                </span>
                {f.machine_confidence !== undefined && (
                  <span>
                    机器置信：{Math.round(f.machine_confidence * 100)}%
                  </span>
                )}
              </div>
            </div>
            <div className="fact-actions">
              {!["user_confirmed", "user_rejected"].includes(
                f.review_status,
              ) && (
                <>
                  <Button
                    onClick={() => act.mutate({ id: f.id, action: "confirm" })}
                  >
                    <Check size={15} />
                    确认
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setEditing(f);
                      setValue(f.normalized_value || f.object_value || "");
                    }}
                  >
                    修改
                  </Button>
                  <Button
                    variant="quiet"
                    onClick={() => act.mutate({ id: f.id, action: "reject" })}
                  >
                    <X size={15} />
                    拒绝
                  </Button>
                </>
              )}
            </div>
          </article>
        ))}
      </div>
      {!q.isLoading && !q.data?.length && (
        <Empty
          title="没有待核验事实"
          body="请先在证据库运行解析；机器提取结果会在这里逐条等待确认。"
        />
      )}
      {editing && (
        <div className="modal-backdrop">
          <div className="modal" role="dialog" aria-modal="true">
            <h2>修改并确认事实</h2>
            <p>原始提取结果仍会保留在审计记录中。</p>
            <textarea
              rows={5}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoFocus
            />
            <div className="form-actions">
              <Button variant="quiet" onClick={() => setEditing(undefined)}>
                取消
              </Button>
              <Button
                onClick={() =>
                  act.mutate({ id: editing.id, action: "edit", value })
                }
              >
                保存并确认
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
function statusText(s: string) {
  return (
    (
      {
        unreviewed: "未复核",
        machine_extracted: "机器提取",
        user_confirmed: "用户已确认",
        user_rejected: "用户已拒绝",
        conflicted: "存在冲突",
        superseded: "已被替代",
      } as Record<string, string>
    )[s] || s
  );
}
function TimelineView({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["timeline", caseId],
    queryFn: () => api<any[]>(`/api/cases/${caseId}/timeline`),
  });
  const rebuild = useMutation({
    mutationFn: () => post(`/api/cases/${caseId}/timeline/rebuild`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["timeline", caseId] }),
  });
  return (
    <div className="content-stack">
      <div className="action-bar">
        <div>
          <h2>已确认事实形成的时间线</h2>
          <p>模糊日期保留原始精度，事件可回溯到证据。</p>
        </div>
        <Button onClick={() => rebuild.mutate()} busy={rebuild.isPending}>
          <RefreshCw size={15} />
          重建时间线
        </Button>
      </div>
      <div className="timeline">
        {q.data?.map((e, i) => (
          <article key={e.id ?? i}>
            <time>
              {e.event_date || "日期待确认"}
              <small>{e.date_precision && ` · ${e.date_precision}`}</small>
            </time>
            <div>
              <Badge
                status={e.user_confirmed ? "user_confirmed" : "unreviewed"}
              >
                {e.user_confirmed ? "已确认" : "待确认"}
              </Badge>
              <h3>{e.title}</h3>
              <p>{e.description}</p>
              <code>{e.source_evidence_id || "来源事实已关联"}</code>
            </div>
          </article>
        ))}
      </div>
      {!q.isLoading && !q.data?.length && (
        <Empty
          title="时间线尚未建立"
          body="确认一部分事实后，运行“重建时间线”生成带来源的事件序列。"
        />
      )}
    </div>
  );
}
function EmploymentView({ caseId }: { caseId: string }) {
  const facts = useQuery({
    queryKey: ["facts", caseId],
    queryFn: () => api<Fact[]>(`/api/cases/${caseId}/facts`),
  });
  const confirmed =
    facts.data?.filter((f) => f.review_status === "user_confirmed") ?? [];
  const groups = [
    {
      name: "主体与管理",
      types: ["management_instruction", "identity", "company_information"],
    },
    {
      name: "报酬与持续性",
      types: ["salary_agreement", "salary_payment", "salary_arrears"],
    },
    {
      name: "工作内容与成果",
      types: ["work_assignment", "attendance", "work_product"],
    },
    { name: "解除与离职", types: ["termination_notice", "resignation"] },
  ];
  return (
    <div className="content-stack">
      <div className="notice neutral">
        <BriefcaseBusiness size={18} />
        <div>
          <strong>劳动关系要素表</strong>
          <p>
            以下只整理支持或反对劳动关系的已确认事实，不代表法律结论或胜诉判断。
          </p>
        </div>
      </div>
      <div className="relation-grid">
        {groups.map((g) => {
          const fs = confirmed.filter((f) =>
            g.types.includes(f.fact_type || ""),
          );
          return (
            <article key={g.name}>
              <header>
                <h3>{g.name}</h3>
                <Badge status={fs.length ? "user_confirmed" : "unreviewed"}>
                  {fs.length ? `${fs.length} 项支持` : "证据不足"}
                </Badge>
              </header>
              {fs.length ? (
                fs.map((f) => (
                  <p key={f.id}>
                    {f.user_corrected_value ||
                      f.normalized_value ||
                      f.object_value}
                    <code>{f.source_evidence_id}</code>
                  </p>
                ))
              ) : (
                <p className="muted">
                  尚无已确认事实。可补充工作安排、汇报关系或转账记录。
                </p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
function WagesView({ caseId }: { caseId: string }) {
  type WageRow = {
    id: string;
    period: string;
    expected_amount: string | number;
    actual_paid_amount: string | number;
    arrears?: string | number;
    payment_date?: string | null;
    payment_method?: string | null;
    confirmation_status?: string | null;
  };
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["wages", caseId],
    queryFn: async () => {
      const result = await api<WageRow[] | { entries: WageRow[] }>(
        `/api/cases/${caseId}/wages`,
      );
      return Array.isArray(result) ? result : (result.entries ?? []);
    },
  });
  const [form, setForm] = useState({
    period: "",
    expected_amount: "",
    paid_amount: "",
    payment_date: "",
    payment_method: "bank_transfer",
    notes: "",
  });
  const add = useMutation({
    mutationFn: () =>
      post(`/api/cases/${caseId}/wages`, {
        period: form.period,
        expected_amount: form.expected_amount,
        paid_amount: form.paid_amount || "0",
        payment_date: form.payment_date || null,
        payer_relationship:
          form.payment_method === "third_party"
            ? "payroll_intermediary"
            : form.payment_method,
        notes: form.notes,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wages", caseId] });
      setForm({ ...form, period: "", expected_amount: "", paid_amount: "" });
    },
  });
  const calc = useMutation({
    mutationFn: () => post(`/api/cases/${caseId}/calculations/recalculate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wages", caseId] }),
  });
  const total =
    q.data?.reduce(
      (n, w) =>
        n +
        Number(
          w.arrears ?? Number(w.expected_amount) - Number(w.actual_paid_amount),
        ),
      0,
    ) ?? 0;
  return (
    <div className="content-stack">
      <div className="wage-total">
        <span>当前欠薪合计</span>
        <strong>
          ¥ {total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
        </strong>
        <Button
          variant="secondary"
          onClick={() => calc.mutate()}
          busy={calc.isPending}
        >
          <RefreshCw size={15} />
          重新计算
        </Button>
        <small>金额由后端确定性函数计算，待用户核对后用于请求。</small>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>期间</th>
              <th>应发</th>
              <th>实付</th>
              <th>欠付</th>
              <th>支付日期</th>
              <th>支付方式</th>
              <th>确认状态</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.map((w) => (
              <tr key={w.id}>
                <td>{w.period}</td>
                <td>¥{w.expected_amount}</td>
                <td>¥{w.actual_paid_amount}</td>
                <td className="amount-due">¥{w.arrears}</td>
                <td>{w.payment_date || "未支付"}</td>
                <td>{w.payment_method || "待确认"}</td>
                <td>
                  <Badge status={w.confirmation_status ?? undefined}>
                    {statusText(w.confirmation_status || "unreviewed")}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="inline-form">
        <h2>新增工资记录</h2>
        <div className="field-grid three">
          <label>
            工资期间
            <input
              type="month"
              value={form.period}
              onChange={(e) => setForm({ ...form, period: e.target.value })}
            />
          </label>
          <label>
            应发金额
            <input
              type="number"
              step="0.01"
              value={form.expected_amount}
              onChange={(e) =>
                setForm({ ...form, expected_amount: e.target.value })
              }
            />
          </label>
          <label>
            实际支付
            <input
              type="number"
              step="0.01"
              value={form.paid_amount}
              onChange={(e) =>
                setForm({ ...form, paid_amount: e.target.value })
              }
            />
          </label>
          <label>
            支付日期
            <input
              type="date"
              value={form.payment_date}
              onChange={(e) =>
                setForm({ ...form, payment_date: e.target.value })
              }
            />
          </label>
          <label>
            支付方式
            <select
              value={form.payment_method}
              onChange={(e) =>
                setForm({ ...form, payment_method: e.target.value })
              }
            >
              <option value="bank_transfer">银行转账</option>
              <option value="third_party">第三人代付</option>
              <option value="cash">现金</option>
              <option value="unknown">暂不清楚</option>
            </select>
          </label>
          <label>
            备注
            <input
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="转账性质、付款人等"
            />
          </label>
        </div>
        <Button
          disabled={!form.period || !form.expected_amount}
          busy={add.isPending}
          onClick={() => add.mutate()}
        >
          <Plus size={15} />
          保存工资记录
        </Button>
        {add.isError && (
          <p className="field-error">{(add.error as Error).message}</p>
        )}
      </section>
    </div>
  );
}
function ClaimsView({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["claims", caseId],
    queryFn: () => api<any[]>(`/api/cases/${caseId}/claims`),
  });
  const [type, setType] = useState("wage_arrears");
  const labels: Record<string, string> = {
    employment_relation: "确认劳动关系",
    wage_arrears: "支付拖欠工资",
    economic_compensation: "支付经济补偿或赔偿",
  };
  const add = useMutation({
    mutationFn: () =>
      post(`/api/cases/${caseId}/claims`, {
        claim_type: type,
        title: labels[type],
        status: "draft",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["claims", caseId] }),
  });
  return (
    <div className="content-stack">
      <div className="claim-add">
        <div>
          <h2>案件可以包含多项请求</h2>
          <p>每项请求分别关联前提事实、证据与计算结果。</p>
        </div>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {Object.entries(labels).map(([v, l]) => (
            <option value={v} key={v}>
              {l}
            </option>
          ))}
        </select>
        <Button onClick={() => add.mutate()} busy={add.isPending}>
          <Plus size={15} />
          新增请求
        </Button>
      </div>
      <div className="claim-list">
        {q.data?.map((c, i) => (
          <article key={c.id}>
            <span className="claim-number">
              请求 {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <h3>{c.title || labels[c.claim_type]}</h3>
              <p>{c.risk_notes || "法律依据、前提事实与支持证据待复核。"}</p>
            </div>
            <strong>
              {c.confirmed_amount ? `¥ ${c.confirmed_amount}` : "金额待确认"}
            </strong>
            <Badge status={c.status}>{c.status || "草拟中"}</Badge>
          </article>
        ))}
      </div>
      {!q.isLoading && !q.data?.length && (
        <Empty
          title="尚未添加仲裁请求"
          body="可添加确认劳动关系、拖欠工资和经济补偿等多项请求。"
        />
      )}
    </div>
  );
}
function WorkflowView({
  caseId,
  kind,
}: {
  caseId: string;
  kind: "gaps" | "review" | "defense";
}) {
  const endpoint =
    kind === "gaps"
      ? "gap-analysis"
      : kind === "review"
        ? "evidence-review"
        : "adversarial-review";
  const title =
    kind === "gaps"
      ? "运行证据缺口检查"
      : kind === "review"
        ? "审查已确认事实的证据质量"
        : "从用人单位角度模拟抗辩";
  const [result, setResult] = useState<any>();
  const run = useMutation({
    mutationFn: () => post(`/api/cases/${caseId}/${endpoint}`),
    onSuccess: setResult,
  });
  const items =
    kind === "review" && result
      ? [
          ...(result.strengths ?? []).map((item: any) => ({ ...item, severity: "strength" })),
          ...(result.weaknesses ?? []).map((item: any) => ({ ...item, severity: "weakness" })),
          ...(result.conflicts ?? []).map((item: any) => ({ ...item, severity: "high" })),
          ...(result.missing_materials ?? []).map((item: any) => ({
            ...item,
            title: item.fact_type,
            description: item.suggestion,
            severity: "missing",
          })),
        ]
      : result?.items ?? result?.checks ?? result?.gaps ?? result?.arguments ?? [];
  return (
    <div className="content-stack">
      <section className="workflow-intro">
        <span>{kind === "gaps" ? "GAP" : kind === "review" ? "审" : "反"}</span>
        <div>
          <h2>{title}</h2>
          <p>
            {kind === "gaps"
              ? "检查请求所需的关键事实是否有证据支撑，并给出可执行的补证建议。"
              : kind === "review"
                ? "只读取用户已确认事实，归纳证据优势、薄弱点、冲突和待补材料，不生成虚假事实。"
                : "识别可能的项目合作、第三人代付、离职原因等抗辩，但不编造对方证据。"}
          </p>
        </div>
        <Button onClick={() => run.mutate()} busy={run.isPending}>
          {run.isPending ? "正在分析" : "开始运行"}
        </Button>
      </section>
      {run.isError && <ErrorState message={(run.error as Error).message} />}{" "}
      {result && (
        <section className="analysis-sheet">
          <header>
            <Badge status="unreviewed">AI 初步识别 · 需要人工复核</Badge>
            <span>生成结果不构成法律意见</span>
          </header>
          {items.length ? (
            items.map((x: any, i: number) => (
              <article key={i}>
                <span>{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3>
                    {x.title ??
                      x.gap_type ??
                      x.topic ??
                      x.possible_argument ??
                      x.argument ??
                      "待关注事项"}
                  </h3>
                  <p>
                    {x.description ??
                      x.suggestion ??
                      x.basis ??
                      x.reasoning ??
                      JSON.stringify(x)}
                  </p>
                  {x.source_evidence_ids && (
                    <code>{x.source_evidence_ids.join(" · ")}</code>
                  )}
                </div>
                <Badge
                  status={x.severity === "high" ? "conflicted" : "unreviewed"}
                >
                  {x.severity ?? "待处理"}
                </Badge>
              </article>
            ))
          ) : (
            <pre>{JSON.stringify(result, null, 2)}</pre>
          )}
        </section>
      )}{" "}
      {!result && !run.isPending && (
        <Empty
          title="尚未运行分析"
          body="分析仅使用当前案件中已有的材料与事实，不会生成不存在的证据。"
        />
      )}
    </div>
  );
}
function DocumentsView({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["documents", caseId],
    queryFn: () => api<any[]>(`/api/cases/${caseId}/documents`),
  });
  const [type, setType] = useState("arbitration_application");
  const gen = useMutation({
    mutationFn: () =>
      post(`/api/cases/${caseId}/documents/generate`, { document_type: type }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", caseId] }),
  });
  return (
    <div className="split-view documents">
      <section>
        <div className="claim-add">
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="arbitration_application">仲裁申请书</option>
            <option value="case_summary">事实摘要</option>
            <option value="evidence_catalog">证据目录</option>
            <option value="wage_schedule">欠薪明细</option>
          </select>
          <Button onClick={() => gen.mutate()} busy={gen.isPending}>
            生成新版本
          </Button>
        </div>
        <div className="document-list">
          {q.data?.map((d) => (
            <article key={d.id}>
              <FileText />
              <div>
                <strong>{d.document_type}</strong>
                <small>
                  版本 v{d.version} · {d.review_status || "待复核"}
                </small>
              </div>
              <Badge status={d.review_status}>
                {d.review_status || "待复核"}
              </Badge>
            </article>
          ))}
        </div>
        {!q.isLoading && !q.data?.length && (
          <Empty
            title="还没有文书草稿"
            body="文书只会使用用户已确认的事实；缺失内容将保留为待确认占位符。"
          />
        )}
      </section>
      <aside className="inspector">
        <h2>生成前规则</h2>
        <ol className="rule-list">
          <li>
            <Check />
            仅使用 user_confirmed 事实
          </li>
          <li>
            <Check />
            金额必须来自工资明细计算
          </li>
          <li>
            <Check />
            关键陈述尽量关联证据
          </li>
          <li>
            <AlertTriangle />
            法律依据仍需专业人员复核
          </li>
        </ol>
        <div className="notice warning">
          <AlertTriangle />
          <p>重新生成会创建新版本，不会覆盖已复核草稿。</p>
        </div>
      </aside>
    </div>
  );
}
export function ExportView({ caseId }: { caseId: string }) {
  const [format, setFormat] = useState("zip");
  const [url, setUrl] = useState<string>();
  const [filingPack, setFilingPack] = useState<{
    url: string;
    filename: string;
  }>();
  const run = useMutation({
    mutationFn: async () => {
      const created = await api<{ filename: string }>(
        `/api/cases/${caseId}/export`,
        {
          method: "POST",
          body: JSON.stringify({ format, redact_sensitive: true }),
          headers: { "Content-Type": "application/json" },
        },
      );
      return api<Blob>(
        `/api/cases/${caseId}/exports/${encodeURIComponent(created.filename)}`,
      );
    },
    onSuccess: (b) => setUrl(URL.createObjectURL(b)),
  });
  const filing = useMutation({
    mutationFn: async () => {
      const created = await api<{ filename: string }>(
        `/api/cases/${caseId}/filing-pack`,
        { method: "POST" },
      );
      const blob = await api<Blob>(
        `/api/cases/${caseId}/exports/${encodeURIComponent(created.filename)}`,
      );
      return {
        filename: created.filename,
        url: URL.createObjectURL(blob),
      };
    },
    onSuccess: setFilingPack,
  });
  return (
    <div className="content-stack">
      <section className="filing-pack-panel">
        <div className="filing-pack-mark">
          <ClipboardCheck size={24} />
        </div>
        <div className="filing-pack-copy">
          <p className="eyebrow">OFFLINE FILING KIT</p>
          <h2>线下立案材料包</h2>
          <p>
            用案件中已填写的信息预填申请书、送达地址确认书、证据清单、案件要素表和办理核对清单，减少现场重复抄写。
          </p>
          <div className="filing-pack-files" aria-label="材料包内容">
            <span>申请书</span>
            <span>送达确认</span>
            <span>证据清单</span>
            <span>案件要素</span>
            <span>办理核对</span>
          </div>
          <div className="notice warning filing-pack-warning">
            <AlertTriangle size={16} />
            <p>
              字段结构参考北京市朝阳区公开材料；文件为辅助预填版，缺失项保留空白，提交份数、签章和送达方式请以拟提交仲裁机构最新要求为准。
            </p>
          </div>
        </div>
        <div className="filing-pack-action">
          <Button onClick={() => filing.mutate()} busy={filing.isPending}>
            <Download size={16} />
            生成线下预填包
          </Button>
          {filingPack && (
            <a
              className="button button-secondary"
              href={filingPack.url}
              download={filingPack.filename}
            >
              下载线下立案材料包
            </a>
          )}
          {filing.isError && (
            <p className="field-error">{(filing.error as Error).message}</p>
          )}
        </div>
      </section>
      <section className="export-panel">
        <FileArchive />
        <div>
          <p className="eyebrow">CASE ARCHIVE EXPORT</p>
          <h2>导出案件档案包</h2>
          <p>
            导出前会运行安全检查。未确认事实不会进入正式文书，OCR
            原文与审计记录单独保存。
          </p>
        </div>
        <div className="export-choice">
          {["zip", "xlsx", "csv", "json"].map((x) => (
            <label key={x}>
              <input
                type="radio"
                value={x}
                checked={format === x}
                onChange={() => setFormat(x)}
              />
              <span>{x.toUpperCase()}</span>
            </label>
          ))}
        </div>
        <label className="check">
          <input type="checkbox" defaultChecked />
          <span>导出时脱敏身份证号、手机号等敏感信息</span>
        </label>
        <Button onClick={() => run.mutate()} busy={run.isPending}>
          <Download size={16} />
          生成{format.toUpperCase()}导出
        </Button>
        {url && (
          <a
            className="button button-secondary"
            href={url}
            download={`case-${caseId}.${format}`}
          >
            下载已生成文件
          </a>
        )}
        {run.isError && (
          <p className="field-error">{(run.error as Error).message}</p>
        )}
      </section>
    </div>
  );
}
function SelfCheck() {
  const q = useQuery({
    queryKey: ["self-check"],
    queryFn: () => api<any>("/api/system/self-check"),
  });
  const checks = Array.isArray(q.data) ? q.data : (q.data?.checks ?? []);
  return (
    <div className="content-stack">
      <div className="action-bar">
        <div>
          <h2>运行环境与导出能力</h2>
          <p>每项检查都给出明确状态和可执行的修复建议。</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => q.refetch()}
          busy={q.isFetching}
        >
          <RefreshCw size={15} />
          重新检查
        </Button>
      </div>
      {q.isError && (
        <ErrorState
          message={(q.error as Error).message}
          retry={() => q.refetch()}
        />
      )}
      <div className="check-list">
        {checks.map((c: any, i: number) => (
          <article key={c.name ?? i} className={`check-${c.status}`}>
            <StatusIcon status={c.status} />
            <div>
              <strong>{c.label ?? c.name}</strong>
              <p>{c.message ?? c.detail}</p>
            </div>
            <Badge status={c.status}>{c.status}</Badge>
            {c.suggestion && <small>{c.suggestion}</small>}
          </article>
        ))}
      </div>
      {!q.isLoading && !checks.length && !q.isError && (
        <Empty
          title="服务未返回检查项"
          body="确认后端已实现 /api/system/self-check，并重新运行检查。"
        />
      )}
    </div>
  );
}
