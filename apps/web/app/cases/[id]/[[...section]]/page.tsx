import { CaseWorkspace } from "@/components/case-workspace";
export default async function CasePage({
  params,
}: {
  params: Promise<{ id: string; section?: string[] }>;
}) {
  const { id, section } = await params;
  return <CaseWorkspace caseId={id} section={section?.[0] ?? "overview"} />;
}
