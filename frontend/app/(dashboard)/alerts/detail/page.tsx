"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AlertView from "./view";

function AlertDetail() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  return <AlertView id={id} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AlertDetail />
    </Suspense>
  );
}
