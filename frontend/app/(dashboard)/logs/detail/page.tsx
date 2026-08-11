"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import LogView from "./view";

function LogDetail() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  return <LogView id={id} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <LogDetail />
    </Suspense>
  );
}
