"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AgentView from "./view";

function AgentDetail() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  return <AgentView id={id} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AgentDetail />
    </Suspense>
  );
}
