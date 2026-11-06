"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui";
import { post } from "@/lib/api";
const schema = z.object({
  worker_name: z.string().min(1, "请填写劳动者称呼，可使用化名"),
  company_name: z.string().min(1, "请填写用人单位名称"),
  employment_start_date: z.string().optional(),
  employment_end_date: z.string().optional(),
  salary: z.coerce.number().nonnegative().optional(),
  payment_status: z.string(),
  social_insurance: z.string(),
  dispute: z.string().min(1, "请简述当前争议"),
  evidence_types: z.string().optional(),
  claims: z.array(z.string()).min(1, "请至少选择一项请求"),
});
type Form = z.infer<typeof schema>;
const steps = ["双方信息", "劳动与工资", "争议情况", "证据与请求"];
export default function NewCase() {
  const [step, setStep] = useState(0);
  const router = useRouter();
  const {
    register,
    handleSubmit,
    trigger,
    formState: { errors },
    watch,
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      payment_status: "暂不清楚",
      social_insurance: "暂不清楚",
      claims: [],
    },
  });
  const create = useMutation({
    mutationFn: async (v: Form) => {
      const created = await post("/api/cases", {
        title: `${v.worker_name}与${v.company_name}劳动争议`,
        case_type: "labor_dispute",
        summary: v.dispute,
        jurisdiction_region: "待确认",
        employment_start_date: v.employment_start_date || null,
        employment_end_date: v.employment_end_date || null,
        parties: [
          { party_type: "worker", name: v.worker_name },
          { party_type: "company", name: v.company_name },
        ],
      });
      const claimTitles: Record<string, string> = {
        employment_relation: "确认劳动关系",
        wage_arrears: "支付拖欠工资",
        economic_compensation: "支付经济补偿或赔偿",
      };
      await Promise.all(
        v.claims.map((claimType) =>
          post(`/api/cases/${created.id}/claims`, {
            claim_type: claimType,
            title: claimTitles[claimType],
            status: "draft",
          }),
        ),
      );
      return created;
    },
    onSuccess: (d) => router.push(`/cases/${d.id}`),
  });
  const fields: Record<number, (keyof Form)[]> = {
    0: ["worker_name", "company_name"],
    1: [],
    2: ["dispute"],
    3: ["claims"],
  };
  async function next() {
    if (await trigger(fields[step])) setStep((x) => Math.min(3, x + 1));
  }
  return (
    <main className="wizard-shell">
      <Link href="/" className="back-link">
        <ArrowLeft size={16} />
        返回首页
      </Link>
      <div className="wizard-head">
        <p className="eyebrow">NEW CASE · 建立卷宗</p>
        <h1>先记录已知信息，不确定的可以稍后补充。</h1>
        <p>这些内容用于建立案件骨架；机器不会把它们直接当作已确认事实。</p>
      </div>
      <div className="wizard-layout">
        <nav className="wizard-steps" aria-label="新建案件步骤">
          {steps.map((s, i) => (
            <button
              key={s}
              className={i === step ? "active" : i < step ? "done" : ""}
              onClick={() => i < step && setStep(i)}
              disabled={i > step}
            >
              <span>{i < step ? <Check size={15} /> : i + 1}</span>
              {s}
              <ChevronRight size={14} />
            </button>
          ))}
        </nav>
        <form
          className="form-paper"
          onSubmit={handleSubmit((v) => create.mutate(v))}
        >
          {step === 0 && (
            <fieldset>
              <legend>双方信息</legend>
              <label>
                劳动者称呼
                <input
                  {...register("worker_name")}
                  placeholder="例如：测试用户甲（可使用化名）"
                />
              </label>
              {errors.worker_name && (
                <p className="field-error">{errors.worker_name.message}</p>
              )}
              <label>
                用人单位
                <input
                  {...register("company_name")}
                  placeholder="请输入单位名称"
                />
              </label>
              {errors.company_name && (
                <p className="field-error">{errors.company_name.message}</p>
              )}
            </fieldset>
          )}
          {step === 1 && (
            <fieldset>
              <legend>劳动与工资</legend>
              <div className="field-grid">
                <label>
                  开始工作日期
                  <input type="date" {...register("employment_start_date")} />
                </label>
                <label>
                  结束日期（可空）
                  <input type="date" {...register("employment_end_date")} />
                </label>
              </div>
              <label>
                约定月工资（元）
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  {...register("salary")}
                  placeholder="暂不清楚可留空"
                />
              </label>
              <label>
                发薪情况
                <select {...register("payment_status")}>
                  <option>暂不清楚</option>
                  <option>部分月份拖欠</option>
                  <option>完全未支付</option>
                  <option>发放日期不固定</option>
                </select>
              </label>
              <label>
                社保情况
                <select {...register("social_insurance")}>
                  <option>暂不清楚</option>
                  <option>正常缴纳</option>
                  <option>晚于实际工作时间缴纳</option>
                  <option>已停缴</option>
                  <option>从未缴纳</option>
                </select>
              </label>
            </fieldset>
          )}
          {step === 2 && (
            <fieldset>
              <legend>当前争议</legend>
              <label>
                请用自己的话描述
                <textarea
                  rows={8}
                  {...register("dispute")}
                  placeholder="例如：公司从 2026 年 2 月开始拖欠工资，并于 5 月停止缴纳社保……"
                />
              </label>
              {errors.dispute && (
                <p className="field-error">{errors.dispute.message}</p>
              )}
              <p className="form-note">
                不用写法律术语。日期、金额或事实暂不清楚时，可直接写“暂不清楚”。
              </p>
            </fieldset>
          )}
          {step === 3 && (
            <fieldset>
              <legend>已有证据与目标请求</legend>
              <label>
                已有证据类型
                <textarea
                  rows={4}
                  {...register("evidence_types")}
                  placeholder="例如：微信截图、银行流水、社保记录、工作成果"
                />
              </label>
              <div className="check-group">
                <span>目标请求（可多选）</span>
                {[
                  ["employment_relation", "确认劳动关系"],
                  ["wage_arrears", "支付拖欠工资"],
                  ["economic_compensation", "支付经济补偿或赔偿"],
                ].map(([v, l]) => (
                  <label className="check" key={v}>
                    <input type="checkbox" value={v} {...register("claims")} />
                    <span>{l}</span>
                  </label>
                ))}
              </div>
              {errors.claims && (
                <p className="field-error">{errors.claims.message}</p>
              )}
            </fieldset>
          )}
          <div className="form-actions">
            <Button
              type="button"
              variant="quiet"
              disabled={step === 0}
              onClick={() => setStep((x) => x - 1)}
            >
              上一步
            </Button>
            <span>
              {step + 1} / {steps.length}
            </span>
            {step < 3 ? (
              <Button type="button" onClick={next}>
                下一步
                <ArrowRight size={16} />
              </Button>
            ) : (
              <Button type="submit" busy={create.isPending}>
                建立案件卷宗
              </Button>
            )}
          </div>
          {create.isError && (
            <p className="field-error">{(create.error as Error).message}</p>
          )}
        </form>
      </div>
    </main>
  );
}
