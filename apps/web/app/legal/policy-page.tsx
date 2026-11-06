import Link from "next/link";

export function PolicyPage({
  kicker,
  title,
  version,
  children,
}: {
  kicker: string;
  title: string;
  version: string;
  children: React.ReactNode;
}) {
  const publisher = process.env.PUBLISHER_NAME || "发行主体待配置";
  const support = process.env.SUPPORT_EMAIL || "支持邮箱待配置";
  return (
    <main className="policy-page">
      <article>
        <Link href="/" className="policy-back">← 返回工作台</Link>
        <p className="section-kicker">{kicker}</p>
        <h1>{title}</h1>
        <div className="policy-meta">
          <span>版本：{version}</span>
          <span>发行主体：{publisher}</span>
          <span>联系方式：{support}</span>
        </div>
        {children}
      </article>
    </main>
  );
}
