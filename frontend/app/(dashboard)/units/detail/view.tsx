"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Cpu, HardDrive } from "lucide-react";
import { unitService, logService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { PageError, PageLoading, PageEmpty } from "@/components/shared/page-states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatNumber, timeAgo, cn } from "@/lib/utils";
import { UnitRiskBadge } from "@/components/shared/unit-risk-badge";

export default function UnitDetailPage({ id }: { id: string }) {
  const [tab, setTab] = useState<"events" | "alerts">("events");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["units", "detail", id],
    queryFn: () => unitService.detail(id),
  });

  const { data: agents } = useQuery({
    queryKey: ["units", id, "agents"],
    queryFn: () => import("@/services").then(({ agentService }) => agentService.list({ unit_id: id })),
    enabled: !!data,
  });

  const { data: events } = useQuery({
    queryKey: ["units", id, "events"],
    queryFn: () => logService.list({ unit_id: id, page: 1, page_size: 15 }),
    enabled: tab === "events" && !!data,
  });

  const { data: alerts } = useQuery({
    queryKey: ["units", id, "alerts"],
    queryFn: () => import("@/services").then(({ alertService }) => alertService.list({ unit_id: id, status: "open", page: 1, page_size: 15 })),
    enabled: tab === "alerts" && !!data,
  });

  return (
    <div>
      <PageHeader
        title={data?.unit.name ?? "Unit Detail"}
        description={data?.unit.unit_code}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/units">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Units
            </Link>
          </Button>
        }
      />

      {isLoading && <PageLoading rows={8} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}

      {data && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Agents" value={formatNumber(data.agent_count)} />
            <StatCard label="Agents Online" value={formatNumber(data.agents_online)} accent />
            <StatCard label="Events (24h)" value={formatNumber(data.event_count_24h)} />
            <StatCard label="Alerts (24h)" value={formatNumber(data.alert_count_24h)} warn={data.alert_count_24h > 0} />
            <StatCard label="Open Alerts" value={formatNumber(data.open_alert_count)} warn={data.open_alert_count > 0} />
          </div>

          <Card className="mb-4">
            <CardHeader className="pb-1">
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-accent" />
                Unit Profile
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Status</p>
                  <StatusBadge status={data.unit.status} className="mt-1" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Region</p>
                  <p className="mt-0.5 text-sm text-foreground">{data.unit.region ?? "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">City / State</p>
                  <p className="mt-0.5 text-sm text-foreground">{[data.unit.city, data.unit.state].filter(Boolean).join(", ") || "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Risk Score</p>
                  <div className="mt-0.5"><UnitRiskBadge risk={data.risk_score} /></div>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="mb-4">
            <div className="flex items-center gap-1 rounded-md border border-border bg-surface p-1 w-fit">
              {(["events", "alerts"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    "rounded px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                    tab === t ? "bg-surface2 text-foreground" : "text-muted hover:text-foreground",
                  )}
                >
                  {t === "events" ? "Recent Events" : "Active Alerts"}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="xl:col-span-2">
              {tab === "events" ? (
                <Card>
                  <CardHeader className="pb-1">
                    <CardTitle>Recent Events</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    {events && events.items.length === 0 && <div className="p-4"><PageEmpty title="No events for this unit" /></div>}
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Time</TableHead>
                          <TableHead>Event</TableHead>
                          <TableHead>Host</TableHead>
                          <TableHead>User</TableHead>
                          <TableHead>Severity</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {events?.items.map((e) => (
                          <TableRow key={e.id}>
                            <TableCell>
                              <Link href={`/logs/detail?id=${e.id}`} className="font-mono text-[11px] text-muted hover:text-accent">
                                {timeAgo(e.timestamp)}
                              </Link>
                            </TableCell>
                            <TableCell className="font-mono text-[12px] text-accent">{e.event_id}</TableCell>
                            <TableCell className="font-mono text-[11px]">{e.hostname ?? "—"}</TableCell>
                            <TableCell className="font-mono text-[11px] text-muted">{e.username ?? "—"}</TableCell>
                            <TableCell><SeverityBadge severity={e.severity} className="text-[9px]" /></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardHeader className="pb-1">
                    <CardTitle>Active Alerts</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Alert</TableHead>
                          <TableHead>Severity</TableHead>
                          <TableHead>Host</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {alerts?.items.map((alert) => (
                          <TableRow key={alert.id}>
                            <TableCell>
                              <Link href={`/alerts/detail?id=${alert.alert_id}`} className="hover:text-accent">
                                <span className="block max-w-[280px] truncate text-[13px] text-foreground">{alert.title}</span>
                                <span className="block font-mono text-[10px] text-muted">{alert.alert_id}</span>
                              </Link>
                            </TableCell>
                            <TableCell><SeverityBadge severity={alert.severity} className="text-[9px]" /></TableCell>
                            <TableCell className="font-mono text-[11px]">{alert.hostname ?? "—"}</TableCell>
                            <TableCell><StatusBadge status={alert.status} className="text-[9px]" /></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              )}
            </div>

            <Card className="h-fit">
              <CardHeader className="pb-1">
                <CardTitle>Agents ({agents?.length ?? 0})</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Host</TableHead>
                      <TableHead className="text-right">CPU</TableHead>
                      <TableHead className="text-right">RAM</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {agents?.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell>
                          <Link href="/agents" className="hover:text-accent">
                            <span className="block font-mono text-[11px] text-foreground">{a.hostname}</span>
                            <span className="block text-[10px] text-muted">{a.ip_address}</span>
                          </Link>
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs"><Cpu className="inline h-3 w-3 text-muted" /> {a.cpu_usage.toFixed(0)}%</TableCell>
                        <TableCell className="text-right font-mono text-xs"><HardDrive className="inline h-3 w-3 text-muted" /> {a.memory_usage.toFixed(0)}%</TableCell>
                        <TableCell><StatusBadge status={a.status} className="text-[9px]" /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, accent, warn }: { label: string; value: string; accent?: boolean; warn?: boolean }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
        <p
          className={cn(
            "mt-1 font-mono text-2xl font-semibold",
            warn ? "text-critical" : accent ? "text-accent" : "text-foreground",
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
