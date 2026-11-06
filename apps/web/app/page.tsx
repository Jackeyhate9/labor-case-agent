"use client";
import Link from "next/link";
import {
  ArrowRight,
  Database,
  FolderOpen,
  Plus,
  ShieldCheck,
  WifiOff,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { EvidenceChain } from "@/components/evidence-chain";
import { Badge, Empty, ErrorState } from "@/components/ui";
import { api, listCases } from "@/lib/api";
export default function Home() {
  const cases = useQuery({ queryKey: ["cases"], queryFn: listCases });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<any>("/api/system/health"),
  });
  return (
    <main className="home-shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">可信材料 · 可追溯事实 · 由你确认</p>
          <h1>
            把散落的证据，
            <br />
            整理成一份可核验的案件卷宗。
          </h1>
          <p className="lead">
            从聊天截图、工资流水到劳动合同，每一项事实都保留来源。机器只提取候选内容，是否成立由你决定。
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/cases/new">
              <Plus size={17} />
              新建案件
            </Link>
            <a className="button button-secondary" href="#recent">
              <FolderOpen size={17} />
              打开已有案件
            </a>
          </div>
        </div>
        <aside className="system-slip">
          <span className="slip-label">当前工作环境</span>
          <dl>
            <div>
              <dt>API 服务</dt>
              <dd>
                <Badge
                  status={health.isSuccess ? "user_confirmed" : "unreviewed"}
                >
                  {health.isLoading
                    ? "检查中"
                    : health.isSuccess
                      ? "已连接"
                      : "未连接"}
                </Badge>
              </dd>
            </div>
            <div>
              <dt>AI 能力</dt>
              <dd>以服务端配置为准</dd>
            </div>
            <div>
              <dt>OCR</dt>
              <dd>支持失败后手工录入</dd>
            </div>
            <div>
              <dt>存储位置</dt>
              <dd>
                <Database size={14} />
                本机 data/cases
              </dd>
            </div>
          </dl>
          <p>
            <ShieldCheck size={16} />
            材料默认保存在本地；启用云模型前，请确认发送范围。
          </p>
        </aside>
      </section>
      <EvidenceChain active="raw" />
      <section id="recent" className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">RECENT DOSSIERS</p>
            <h2>最近案件</h2>
          </div>
          <Link href="/cases/new">
            建立新卷宗 <ArrowRight size={15} />
          </Link>
        </div>
        {cases.isError ? (
          <ErrorState
            message={(cases.error as Error).message}
            retry={() => cases.refetch()}
          />
        ) : cases.data?.length ? (
          <div className="case-list">
            {cases.data.map((c) => (
              <Link href={`/cases/${c.id}`} className="case-row" key={c.id}>
                <span className="case-file-mark">案</span>
                <span className="case-main">
                  <strong>{c.title}</strong>
                  <small>
                    {c.jurisdiction_region || "管辖地待确认"} ·{" "}
                    {c.case_type || "劳动争议"}
                  </small>
                </span>
                <Badge status={c.status}>{c.status || "整理中"}</Badge>
                <span className="case-date">
                  {c.updated_at?.slice(0, 10) || "刚刚更新"}
                </span>
                <ArrowRight size={17} />
              </Link>
            ))}
          </div>
        ) : (
          !cases.isLoading && (
            <Empty
              title="还没有案件卷宗"
              body="新建案件后，可逐步上传证据、确认事实并生成文书。"
              action={
                <Link href="/cases/new" className="button button-primary">
                  新建第一个案件
                </Link>
              }
            />
          )
        )}
      </section>
      <section className="boundary-grid">
        <article>
          <WifiOff />
          <h3>离线也能继续整理</h3>
          <p>
            模型不可用时，证据上传、手工录入、时间线编辑和金额计算仍可继续。
          </p>
        </article>
        <article>
          <ShieldCheck />
          <h3>明确的法律边界</h3>
          <p>系统不会承诺胜诉，也不会把未确认的 OCR 内容自动写入正式文书。</p>
        </article>
      </section>
    </main>
  );
}
