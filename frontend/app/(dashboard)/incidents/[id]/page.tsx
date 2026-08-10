import IncidentView from "./view";
import { generateStaticParamsFor } from "@/lib/static-params";

export function generateStaticParams() {
  return generateStaticParamsFor("incidents");
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <IncidentView id={id} />;
}
