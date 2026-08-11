"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import type { ActiveThreat } from "@/types";
import { timeAgo, severityColor } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { PageEmpty } from "@/components/shared/page-states";
import { Progress } from "@/components/ui/progress";

export function ActiveThreats({ threats }: { threats: ActiveThreat[] }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-critical" />
          Active Threats
        </CardTitle>
      </CardHeader>
      <CardContent>
        {threats.length === 0 ? (
          <PageEmpty title="No active threats" description="Open alerts will appear here." />
        ) : (
          <div className="divide-y divide-border/60">
            {threats.slice(0, 8).map((threat) => {
              const sc = severityColor(threat.severity);
              return (
                <Link
                  key={threat.id}
                  href={`/alerts/detail?id=${threat.alert_id}`}
                  className="block py-2.5 transition-colors hover:bg-surface2/40"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-medium text-foreground">{threat.title}</p>
                      <p className="mt-0.5 truncate font-mono text-[11px] text-muted">
                        {threat.hostname ?? "unknown host"}
                        {threat.source_ip ? ` · ${threat.source_ip}` : ""}
                        {threat.username ? ` · ${threat.username}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <SeverityBadge severity={threat.severity} />
                      <span className="text-[10px] text-muted">{timeAgo(threat.detected_at)}</span>
                    </div>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <Progress value={threat.risk_score} colorClass={`${sc.dot} opacity-70`} className="h-1 flex-1" />
                    <span className="font-mono text-[10px] text-muted">{threat.risk_score}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
