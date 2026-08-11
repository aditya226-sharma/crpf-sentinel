"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import UnitView from "./view";

function UnitDetail() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  return <UnitView id={id} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <UnitDetail />
    </Suspense>
  );
}
