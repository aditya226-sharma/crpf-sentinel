import LogView from "./view";
import { generateStaticParamsFor } from "@/lib/static-params";

export function generateStaticParams() {
  return generateStaticParamsFor("logs");
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LogView id={id} />;
}
