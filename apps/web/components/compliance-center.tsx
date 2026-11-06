"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { FileCheck2, ShieldX } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ComplianceStatus } from "./compliance-gate";
import { Badge, Button, ErrorState } from "./ui";

export function ComplianceCenter() {
  const status = useQuery({
    queryKey: ["compliance"],
    queryFn: () => api<ComplianceStatus>("/api/system/compliance"),
  });
  const withdraw = useMutation({
    mutationFn: () =>
      api("/api/system/compliance/consent", { method: "DELETE" }),
    onSuccess: () => window.location.assign("/"),
  });

  return (
    <section className="compliance-center" aria-labelledby="compliance-center-title">
      <header>
        <div>
          <p className="section-kicker">POLICY CONTROL</p>
          <h2 id="compliance-center-title">协议、隐私与 AI 处理说明</h2>
          <p>查看当前接受记录；撤回后将回到首次使用确认页，但仍可备份或清除本机数据。</p>
        </div>
        <FileCheck2 aria-hidden="true" />
      </header>
      {status.isError ? (
        <ErrorState message={(status.error as Error).message} retry={() => status.refetch()} />
      ) : status.data ? (
        <>
          <div className="policy-status">
            <Badge status={status.data.accepted ? "passed" : "unreviewed"}>
              {status.data.accepted ? "当前版本已接受" : "尚未接受"}
            </Badge>
            <span>
              {status.data.accepted_at
                ? `接受时间：${new Date(status.data.accepted_at).toLocaleString("zh-CN")}`
                : "没有当前版本的接受记录"}
            </span>
          </div>
          <nav className="policy-links" aria-label="法律文件">
            {(status.data.documents ?? []).map((document) => (
              <Link key={document.id} href={document.href} target="_blank">
                {document.title}
              </Link>
            ))}
          </nav>
          {status.data.accepted && (
            <Button variant="secondary" busy={withdraw.isPending} onClick={() => withdraw.mutate()}>
              <ShieldX aria-hidden="true" />
              撤回当前版本同意
            </Button>
          )}
          {withdraw.isError && <p className="field-error">{(withdraw.error as Error).message}</p>}
        </>
      ) : null}
    </section>
  );
}
