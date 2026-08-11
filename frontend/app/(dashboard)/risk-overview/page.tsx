"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, Gauge, Radio, AlertTriangle, ShieldAlert, Globe, MonitorSmartphone } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dashboardService, unitService, analyticsService, statsService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Mono } from "@/components/shared/mono";
import { StatusBadge } from "@/components/shared/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { formatCompact, cn } from "@/lib/utils";

const riskTone = (risk: number) => {
  if (risk >= 60) return { text: "text-critical", bar: "bg-critical", label: "CRITICAL" };
  if (risk >= 35) return { text: "text-medium", bar: "bg-medium", label: "ELEVATED" };
  return { text: "text-success", bar: "bg-success", label: "STABLE" };
};

export default function RiskOverviewPage() {
  const unitsQuery = useQuery({ queryKey: ["units"], queryFn: () => unitService.list() });
  const overviewQuery = useQuery({
    queryKey: ["dashboard", "unit-overview"],
    queryFn: () => dashboardService.unitOverview(),
  });
  const topQuery = useQuery({ queryKey: ["analytics", "top"], queryFn: () => analyticsService.top() });
  const statsQuery = useQuery({ queryKey: ["stats"], queryFn: () => statsService.get() });

  const loading = unitsQuery.isLoading || overviewQuery.isLoading;
  const error = unitsQuery.isError || overviewQuery.isError || topQuery.isError || statsQuery.isError;

  const regionMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const u of unitsQuery.data ?? []) m[u.id] = u.region ?? u.city ?? "—";
    return m;
  }, [unitsQuery.data]);

  const byRegion = useMemo(() => {
    const agg = new Map<string, { count: number; riskSum: number; critical: number; agents: number }>();
    for (const u of overviewQuery.data ?? []) {
      const region = regionMap[u.id] ?? "OTHER";
      const cur = agg.get(region) ?? { count: 0, riskSum: 0, critical: 0, agents: 0 };
      cur.count += 1;
      cur.riskSum += u.risk;
      cur.agents += u.agents;
      if (u.risk >= 60) cur.critical += 1;
      agg.set(region, cur);
    }
    return [...agg.entries()]
      .map(([region, v]) => ({ region, avgRisk: Math.round(v.riskSum / v.count), units: v.count, critical: v.critical, agents: v.agents }))
      .sort((a, b) => b.avgRisk - a.avgRisk);
  }, [overviewQuery.data, regionMap]);

  const highRisk = (overviewQuery.data ?? []).filter((u) => u.risk >= 60).length;
  const elevatedRisk = (overviewQuery.data ?? []).filter((u) => u.risk >= 35 && u.risk < 60).length;

  return (
    <div>
      <PageHeader
        title="Risk Overview"
        description="Consolidated risk posture across all monitored CRPF units and assets."
      />

      {loading && <PageLoading rows={8} />}
      {error && (
        <PageError
          message={(unitsQuery.error as Error)?.message ?? (overviewQuery.error as Error)?.message}
          onRetry={() => {
            void unitsQuery.refetch();
            void overviewQuery.refetch();
            void topQuery.refetch();
            void statsQuery.refetch();
          }}
        />
      )}

      {overviewQuery.data && statsQuery.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "Monitored Units", value: overviewQuery.data.length, icon: Building2, cls: "text-accent" },
              { label: "High Risk Units", value: highRisk, icon: ShieldAlert, cls: "text-critical" },
              { label: "Elevated Risk", value: elevatedRisk, icon: AlertTriangle, cls: "text-medium" },
              { label: "Agents Online", value: `${statsQuery.data.agents_online} / ${statsQuery.data.total_agents}`, icon: Radio, cls: "text-success" },
            ].map((s) => (
              <Card key={s.label}>
                <CardContent className="flex items-center gap-3 p-4">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-surface2">
                    <s.icon className={cn("h-4 w-4", s.cls)} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{s.label}</p>
                    <p className="font-mono text-lg font-semibold leading-tight text-foreground">{s.value}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Gauge className="h-4 w-4 text-accent" />
                  Unit Risk Ranking
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Unit</TableHead>
                      <TableHead className="text-right">Agents</TableHead>
                      <TableHead className="text-right">Events</TableHead>
                      <TableHead className="text-right">Alerts</TableHead>
                      <TableHead className="w-40">Risk</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...overviewQuery.data].sort((a, b) => b.risk - a.risk).map((u) => {
                      const tone = riskTone(u.risk);
                      return (
                        <TableRow key={u.id}>
                          <TableCell>
                            <Link href={`/units/detail?id=${u.id}`} className="hover:text-accent">
                              <span className="font-mono text-[12px] text-accent">{u.unit_code}</span>
                              <span className="block text-[11px] text-muted">{u.name}</span>
                            </Link>
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs">{u.agents}</TableCell>
                          <TableCell className="text-right font-mono text-xs">{formatCompact(u.events)}</TableCell>
                          <TableCell className="text-right font-mono text-xs">{u.alerts}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Progress value={u.risk} colorClass={tone.bar} className="h-1 flex-1" />
                              <span className={cn("w-8 text-right font-mono text-[11px] font-semibold", tone.text)}>{u.risk}</span>
                            </div>
                          </TableCell>
                          <TableCell><StatusBadge status={u.status} className="text-[9px]" /></TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Globe className="h-4 w-4 text-accent" />
                  Regional Risk
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={byRegion} layout="vertical" margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
                      <XAxis type="number" hide domain={[0, 100]} />
                      <YAxis type="category" dataKey="region" width={64} tick={{ fill: "#64748B", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<RegionTooltip />} cursor={{ fill: "rgba(34,211,238,0.05)" }} />
                      <Bar dataKey="avgRisk" radius={[0, 3, 3, 0]} barSize={14}>
                        {byRegion.map((r) => (
                          <Cell key={r.region} fill={r.avgRisk >= 60 ? "#EF4444" : r.avgRisk >= 35 ? "#F59E0B" : "#22C55E"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-3 space-y-1.5 border-t border-border pt-3">
                  {byRegion.slice(0, 5).map((r) => (
                    <div key={r.region} className="flex items-center justify-between text-[11px]">
                      <span className="text-muted">{r.region}</span>
                      <span className="font-mono text-foreground">
                        {r.units} units · <span className={riskTone(r.avgRisk).text}>{r.avgRisk} avg risk</span>
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Globe className="h-4 w-4 text-accent" />
                  Top Source IPs
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 p-4">
                {(topQuery.data?.top_source_ips ?? []).slice(0, 6).map((item, i) => (
                  <div key={item.value} className="flex items-center gap-3">
                    <Badge variant="outline" className="w-5 justify-center font-mono text-[10px]">{i + 1}</Badge>
                    <Mono className="flex-1 truncate text-[12px]">{item.value}</Mono>
                    <span className="font-mono text-xs text-muted">{item.count}</span>
                  </div>
                ))}
                {(topQuery.data?.top_source_ips ?? []).length === 0 && (
                  <p className="py-6 text-center text-xs text-muted">No source IP activity yet.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <MonitorSmartphone className="h-4 w-4 text-accent" />
                  Top Hosts
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 p-4">
                {(topQuery.data?.top_hosts ?? []).slice(0, 6).map((item, i) => (
                  <div key={item.value} className="flex items-center gap-3">
                    <Badge variant="outline" className="w-5 justify-center font-mono text-[10px]">{i + 1}</Badge>
                    <Mono className="flex-1 truncate text-[12px]">{item.value}</Mono>
                    <span className="font-mono text-xs text-muted">{item.count}</span>
                  </div>
                ))}
                {(topQuery.data?.top_hosts ?? []).length === 0 && (
                  <p className="py-6 text-center text-xs text-muted">No host activity yet.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-critical" />
                  Units Requiring Attention
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                {highRisk === 0 ? (
                  <p className="py-6 text-center text-xs text-muted">No high-risk units. System healthy.</p>
                ) : (
                  <div className="space-y-2">
                    {[...overviewQuery.data].filter((u) => u.risk >= 60).map((u) => (
                      <Link key={u.id} href={`/units/detail?id=${u.id}`} className="flex items-center justify-between rounded border border-critical/20 bg-critical/5 px-3 py-2 transition-colors hover:bg-critical/10">
                        <div>
                          <p className="font-mono text-[12px] text-critical">{u.unit_code}</p>
                          <p className="text-[10px] text-muted">{u.name}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-[12px] font-semibold text-critical">{u.risk}</p>
                          <p className="text-[9px] text-muted">{u.alerts} alerts</p>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function RegionTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-surface2 px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-foreground">{item.region}</p>
      <p className="mt-0.5 font-mono text-accent">{item.avgRisk} avg risk</p>
      <p className="text-muted">{item.units} units · {item.agents} agents · {item.critical} critical</p>
    </div>
  );
}
