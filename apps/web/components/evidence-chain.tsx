import { Archive, ScanText, UserCheck, FileText } from "lucide-react";
const levels = [
  { key: "raw", name: "原始材料", hint: "文件与原文", icon: Archive },
  { key: "machine", name: "机器提取", hint: "仍待人工核验", icon: ScanText },
  { key: "confirmed", name: "用户确认", hint: "可进入计算", icon: UserCheck },
  { key: "draft", name: "文书", hint: "复核后导出", icon: FileText },
];
export function EvidenceChain({
  active = "raw",
  compact = false,
}: {
  active?: string;
  compact?: boolean;
}) {
  const activeIndex = Math.max(
    0,
    levels.findIndex((x) => x.key === active),
  );
  return (
    <div
      className={`evidence-chain ${compact ? "compact" : ""}`}
      aria-label="四层证据链"
    >
      {levels.map((level, i) => (
        <div
          className={`chain-level ${i < activeIndex ? "done" : i === activeIndex ? "active" : "pending"}`}
          key={level.key}
        >
          <span className="chain-index">0{i + 1}</span>
          <level.icon size={17} />
          <span>
            <strong>{level.name}</strong>
            {!compact && <small>{level.hint}</small>}
          </span>
        </div>
      ))}
    </div>
  );
}
