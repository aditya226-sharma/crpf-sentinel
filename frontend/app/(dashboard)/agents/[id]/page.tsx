import AgentView from "./view";
import { generateStaticParamsFor } from "@/lib/static-params";

export function generateStaticParams() {
  return generateStaticParamsFor("agents");
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AgentView id={id} />;
}
