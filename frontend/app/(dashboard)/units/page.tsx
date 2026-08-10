"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, MapPin } from "lucide-react";
import { unitService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { PageError, PageLoading, PageEmpty } from "@/components/shared/page-states";
export default function UnitsPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["units", "all"],
    queryFn: () => unitService.list(),
  });

  return (
    <div>
      <PageHeader
        title="Units"
        description="Deployed CRPF units enrolled in the CyberRakshak network."
      />

      {isLoading && <PageLoading rows={8} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}
      {data && data.length === 0 && <PageEmpty title="No units enrolled" />}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((unit) => (
          <Link key={unit.id} href={`/units/${unit.id}`}>
            <Card className="transition-colors hover:border-accent/40">
              <CardHeader className="flex flex-row items-start justify-between pb-1">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface2">
                    <Building2 className="h-5 w-5 text-accent" />
                  </div>
                  <div>
                    <p className="font-mono text-[10px] text-accent">{unit.unit_code}</p>
                    <h3 className="text-sm font-semibold text-foreground">{unit.name}</h3>
                  </div>
                </div>
                <StatusBadge status={unit.status} className="text-[9px]" />
              </CardHeader>
              <CardContent>
                <p className="flex items-center gap-1.5 text-xs text-muted">
                  <MapPin className="h-3.5 w-3.5" />
                  {[unit.city, unit.state].filter(Boolean).join(", ") || unit.region || "Location not set"}
                </p>
                {unit.latitude && unit.longitude && (
                  <p className="mt-1 font-mono text-[10px] text-slate-500">
                    {unit.latitude.toFixed(4)}, {unit.longitude.toFixed(4)}
                  </p>
                )}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
