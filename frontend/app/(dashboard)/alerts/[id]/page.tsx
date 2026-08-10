import AlertView from "./view";
import { generateStaticParamsFor } from "@/lib/static-params";

export function generateStaticParams() {
  return generateStaticParamsFor("alerts");
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AlertView id={id} />;
}
