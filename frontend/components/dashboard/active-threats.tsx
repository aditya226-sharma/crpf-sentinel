"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import type { ActiveThreat } from "@/types";
import { timeAgo, severityColor } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { Progress } from "@/components/ui/progress";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

export function ActiveThreats({ threats }: { threats: ActiveThreat[] }) {
  const severityCounts = threats.reduce<Record<string, number>>((acc, t) => {
    acc[t.severity] = (acc[t.severity] ?? 0) + 1;
    return acc;
  }, {});
  const total = threats.length;
  const investigating = threats.filter((t) => t.status === "investigating").length;
  const avgRisk = total ? Math.round(threats.reduce((sum, t) => sum + t.risk_score, 0) / total) : 0;

  return (
    <Card className="flex h-full min-h-0 flex-col">
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-critical" />
          Active Threats
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 min-h-0 flex-col p-0">
        {threats.length === 0 ? (
          <div className="flex flex-1 items-center justify-center px-3 py-6">
            <div className="text-center">
              <p className="text-xs font-medium text-foreground">All clear on this watch.</p>
              <p className="mt-1 text-[11px] text-muted">No open alerts in scope — new detections will surface here as they land.</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-1 flex-col divide-y divide-border/60">
            {threats.slice(0, 8).map((threat) => {
              const sc = severityColor(threat.severity);
              return (
                <Link
                  key={threat.id}
                  href={`/alerts/detail?id=${threat.alert_id}`}
                  className="flex flex-1 flex-col justify-center px-3 py-2.5 transition-colors hover:bg-surface2/40"
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

        <div className="mt-auto border-t border-border px-3 py-2.5">
          {total > 0 ? (
            <>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">Severity mix</span>
                <span className="font-mono text-[10px] text-muted">
                  {total} open · {investigating} investigating · avg risk <span className="text-amber-400">{avgRisk}</span>
                </span>
              </div>
              <div className="flex h-1.5 w-full gap-px overflow-hidden rounded-full bg-surface2">
                {SEVERITY_ORDER.filter((s) => (severityCounts[s] ?? 0) > 0).map((s) => (
                  <div
                    key={s}
                    className="h-full"
                    style={{ width: `${((severityCounts[s] ?? 0) / total) * 100}%`, background: severityColor(s).hex }}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between text-[10px] text-muted">
              <span>0 open alerts · detection across all units is quiet</span>
            </div>
          )}
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[10px] text-muted">Triage from the watch desk</span>
            <Link href="/alerts" className="text-[10px] text-accent hover:underline">
              Open alert queue →
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}