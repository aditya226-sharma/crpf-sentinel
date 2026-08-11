"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import IncidentView from "./view";

function IncidentDetail() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  return <IncidentView id={id} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <IncidentDetail />
    </Suspense>
  );
}
