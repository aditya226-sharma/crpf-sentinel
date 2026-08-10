"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Flame, ShieldCheck, XCircle } from "lucide-react";
import { alertService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { MitreBadge } from "@/components/shared/mitre-badge";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, severityColor } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

const STATUS_ACTIONS = [
  { status: "investigating", label: "Start Investigation", icon: Flame, variant: "outline" as const },
  { status: "resolved", label: "Resolve", icon: CheckCircle2, variant: "default" as const },
  { status: "false_positive", label: "False Positive", icon: XCircle, variant: "ghost" as const },
];

export default function AlertDetailPage({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [transitioning, setTransitioning] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["alerts", "detail", id],
    queryFn: () => alertService.detail(id),
    refetchInterval: 30000,
  });

  async function transition(status: string) {
    setTransitioning(true);
    try {
      await alertService.update(id, { status });
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
      void refetch();
    } finally {
      setTransitioning(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Alert Detail"
        description={data ? `${data.alert_id} · ${data.rule_name ?? "Correlation Engine"}` : "Loading…"}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/alerts">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Alerts
            </Link>
          </Button>
        }
      />

      {isLoading && <PageLoading rows={10} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}

      {data && (
        <div className="space-y-4">
          <Card>
            <CardContent className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={data.severity} />
                    <StatusBadge status={data.status} />
                    <Badge variant="outline" className="font-mono text-[9px]">{data.alert_id}</Badge>
                  </div>
                  <h2 className="mt-2 text-lg font-semibold text-foreground">{data.title}</h2>
                  <p className="mt-1 max-w-3xl text-sm text-muted">{data.description}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted">
                    <span>Host: <span className="font-mono text-foreground">{data.hostname ?? "—"}</span></span>
                    <span>Source: <span className="font-mono text-foreground">{data.source_ip ?? "—"}</span></span>
                    <span>User: <span className="font-mono text-foreground">{data.username ?? "—"}</span></span>
                    <span>First seen: <span className="font-mono text-foreground">{formatDateTime(data.first_seen)}</span></span>
                    <span>MITRE: <MitreBadge technique={data.mitre_technique} name={data.mitre_name} /></span>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <div className="flex items-center gap-2">
                    <Progress value={data.risk_score} colorClass={severityColor(data.severity).dot} className="h-2 w-40" />
                    <span className="font-mono text-lg font-semibold text-foreground">{data.risk_score}</span>
                  </div>
                  <div className="flex gap-1.5">
                    {STATUS_ACTIONS.filter((a) => a.status !== data.status).map((action) => (
                      <Button
                        key={action.status}
                        variant={action.variant}
                        size="sm"
                        disabled={transitioning}
                        onClick={() => void transition(action.status)}
                      >
                        <action.icon className="h-3.5 w-3.5" />
                        {action.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle>Risk Assessment</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {data.risk_factors && data.risk_factors.length > 0 ? (
                    data.risk_factors.map((f, i) => (
                      <div key={i} className="flex items-center justify-between rounded-md border border-border/60 bg-surface2/40 px-3 py-2">
                        <span className="text-xs text-foreground">{f.label}</span>
                        <span className="font-mono text-xs text-accent">+{f.points}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-muted">No additional risk factors computed.</p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-1">
                <CardTitle>Detection Explanation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-slate-300">
                  {data.detection_explanation ?? "Alert raised by the detection engine."}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-accent" />
                  Recommended Steps
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="list-inside list-decimal space-y-1.5 text-xs text-slate-300">
                  {(data.recommended_steps ?? ["Preserve evidence", "Isolate affected host if needed", "Review related events", "Update detection rules"]).map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-1">
              <CardTitle>Triggering Events ({data.events.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Host</TableHead>
                    <TableHead>Event</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Source IP</TableHead>
                    <TableHead>Severity</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.events.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell>
                        <Link href={`/logs/${e.id}`} className="font-mono text-[11px] text-muted hover:text-accent">
                          {formatDateTime(e.timestamp)}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-[11px] text-foreground">{e.hostname ?? "—"}</TableCell>
                      <TableCell className="font-mono text-[12px] text-accent">{e.event_id}</TableCell>
                      <TableCell className="text-xs text-muted">{e.category?.replace("_", " ") ?? "—"}</TableCell>
                      <TableCell className="font-mono text-[11px]">{e.username ?? "—"}</TableCell>
                      <TableCell className="font-mono text-[11px] text-muted">{e.source_ip ?? "—"}</TableCell>
                      <TableCell><SeverityBadge severity={e.severity} className="text-[9px]" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
