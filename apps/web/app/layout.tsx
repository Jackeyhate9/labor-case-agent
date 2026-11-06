import type { Metadata } from "next";
import Link from "next/link";
import { Scale } from "lucide-react";
import { Providers } from "./providers";
import { ThemeToggle } from "@/components/theme-toggle";
import { ComplianceGate } from "@/components/compliance-gate";
import "./globals.css";
import "./workspace.css";
export const metadata: Metadata = {
  title: "劳动争议案件工作台",
  description: "将劳动争议材料整理成可核验案件事实",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <Providers>
          <ComplianceGate>
            <header className="topbar">
              <Link href="/" className="brand">
                <span className="brand-seal">
                  <Scale size={18} />
                </span>
                <span>
                  <strong>劳动争议案件工作台</strong>
                  <small>LABOR CASE DOSSIER</small>
                </span>
              </Link>
              <div className="top-actions">
                <span className="privacy-dot">本地优先 · 默认不发送材料</span>
                <ThemeToggle />
              </div>
            </header>
            {children}
            <footer>
              <span>
                本系统仅提供材料整理、信息提取、计算辅助和文书草拟，不构成正式法律意见。重要内容必须由本人或专业人员复核。
              </span>
              <nav aria-label="法律与支持">
                <Link href="/legal/terms">用户协议</Link>
                <Link href="/legal/privacy">隐私政策</Link>
                <Link href="/legal/ai-notice">AI 说明</Link>
              </nav>
            </footer>
          </ComplianceGate>
        </Providers>
      </body>
    </html>
  );
}
