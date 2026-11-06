"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { api, post } from "@/lib/api";
import { Button, ErrorState } from "./ui";

export type ComplianceStatus = {
  acceptance_required: boolean;
  accepted: boolean;
  accepted_at?: string | null;
  versions: {
    terms: string;
    privacy: string;
    ai_notice: string;
  };
  publisher: {
    name: string;
    support_email: string;
    configured: boolean;
  };
  documents: Array<{ id: string; title: string; href: string }>;
};

export function ComplianceGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [terms, setTerms] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [aiNotice, setAiNotice] = useState(false);
  const status = useQuery({
    queryKey: ["compliance"],
    queryFn: () => api<ComplianceStatus>("/api/system/compliance"),
    retry: 2,
  });
  const accept = useMutation({
    mutationFn: () => {
      if (!status.data) throw new Error("合规信息尚未载入");
      return post("/api/system/compliance/accept", {
        terms_version: status.data.versions.terms,
        privacy_version: status.data.versions.privacy,
        ai_notice_version: status.data.versions.ai_notice,
        accept_terms: terms,
        accept_sensitive_data_processing: sensitive,
        accept_ai_notice: aiNotice,
      });
    },
    onSuccess: () => status.refetch(),
  });

  if (pathname.startsWith("/legal/")) return children;
  if (status.isLoading) {
    return (
      <main className="compliance-loading" aria-live="polite">
        <ShieldCheck aria-hidden="true" />
        <p>正在核对本机协议版本…</p>
      </main>
    );
  }
  if (status.isError) {
    return (
      <main className="compliance-loading">
        <ErrorState
          message={(status.error as Error).message}
          retry={() => status.refetch()}
        />
      </main>
    );
  }
  if (!status.data?.acceptance_required) return children;

  return (
    <main className="compliance-gate">
      <section aria-labelledby="compliance-title">
        <div className="compliance-mark">
          <ShieldCheck aria-hidden="true" />
        </div>
        <p className="section-kicker">首次使用确认</p>
        <h1 id="compliance-title">先明确数据和自动化处理边界，再开始整理案件。</h1>
        <p className="compliance-lede">
          本工具处理的材料可能包含身份证、金融账户、录音等敏感个人信息。默认数据保存在本机；
          只有你主动选择并确认外部服务后，相关内容才可能离开设备。
        </p>

        {!status.data.publisher.configured && (
          <div className="notice danger" role="alert">
            <div>
              <strong>当前构建尚未配置正式发行主体</strong>
              <p>可用于内部验证，不应作为公开销售包发布。</p>
            </div>
          </div>
        )}

        <nav className="policy-links" aria-label="法律与隐私文件">
          {status.data.documents.map((document) => (
            <Link key={document.id} href={document.href} target="_blank">
              {document.title}
            </Link>
          ))}
        </nav>

        <fieldset className="policy-acknowledgements">
          <legend>需要逐项确认</legend>
          <label>
            <input
              type="checkbox"
              checked={terms}
              onChange={(event) => setTerms(event.target.checked)}
            />
            <span>
              <strong>我已阅读并接受用户服务协议</strong>
              <small>理解本工具不构成正式法律意见，也不保证案件结果。</small>
            </span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={sensitive}
              onChange={(event) => setSensitive(event.target.checked)}
            />
            <span>
              <strong>我确认有权处理所导入的材料</strong>
              <small>并了解材料可能包含敏感个人信息，应采取必要保护措施。</small>
            </span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={aiNotice}
              onChange={(event) => setAiNotice(event.target.checked)}
            />
            <span>
              <strong>我已阅读 AI 与自动化处理说明</strong>
              <small>机器提取、OCR 和生成草稿必须经过人工核验。</small>
            </span>
          </label>
        </fieldset>

        <Button
          busy={accept.isPending}
          disabled={!terms || !sensitive || !aiNotice}
          onClick={() => accept.mutate()}
        >
          接受当前版本并进入工作台
        </Button>
        {accept.isError && (
          <p className="field-error">{(accept.error as Error).message}</p>
        )}
        <p className="compliance-footnote">
          你以后可以在“能力设置”中撤回同意、备份数据或清除全部案件。
        </p>
      </section>
    </main>
  );
}
