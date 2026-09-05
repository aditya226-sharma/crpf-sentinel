"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardService, statsService, incidentService } from "@/services";
import type { KpiValue } from "@/types";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { TimelineChart } from "@/components/charts/timeline-chart";
import { SeverityDonut } from "@/components/charts/severity-donut";
import { ActiveThreats } from "@/components/dashboard/active-threats";
import { LiveEventStream } from "@/components/dashboard/live-event-stream";
import { UnitSecurityMap } from "@/components/dashboard/unit-security-map";
import { StatusBadge } from "@/components/shared/status-badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCompact, cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { Badge } from "@/components/ui/badge";

const PERIODS = [
  { key: "1h", label: "1H" },
  { key: "6h", label: "6H" },
  { key: "24h", label: "24H" },
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const [period, setPeriod] = useState("24h");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard", "summary", period],
    queryFn: () => dashboardService.summary(period),
    refetchInterval: 30000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => statsService.get(),
    refetchInterval: 60000,
  });

  const { data: openIncidents } = useQuery({
    queryKey: ["incidents", "open-count"],
    queryFn: async () => {
      const [open, critical] = await Promise.all([
        incidentService.list({ status: "open", page_size: 1 }),
        incidentService.list({ status: "open", severity: "critical", page_size: 1 }),
      ]);
      return { total: open.meta.total, critical: critical.meta.total };
    },
    refetchInterval: 60000,
  });

  const onlineAgents = Number(String(data?.active_agents.value ?? "").split("/")[0].trim()) || 0;
  const agentsTotal = stats?.total_agents ?? 0;
  const agentsPct = agentsTotal ? Math.round(((stats?.agents_online ?? 0) / agentsTotal) * 1000) / 10 : 0;

  const kpis: { kpi: KpiValue; icon: string; spark?: number[]; valueClassName?: string }[] = data
    ? [
        {
          kpi: data.total_events,
          icon: "Database",
          spark: data.timeline.map((t) => t.events),
        },
        {
          kpi: data.critical_alerts,
          icon: "ShieldAlert",
          valueClassName: "text-critical",
          spark: data.timeline.map((t) => t.critical_alerts),
        },
        {
          kpi: {
            label: "Active Alerts",
            value: stats?.open_alerts ?? data.high_alerts.value,
            change_pct: null,
            compare_label: "open alerts",
            detail: `${stats?.open_alerts ?? 0} open across all units`,
            status: "open",
          },
          icon: "BellRing",
          valueClassName: "text-high",
          spark: data.timeline.map((t) => t.alerts),
        },
        {
          kpi: {
            ...data.active_agents,
            change_pct: null,
            detail: `${agentsPct}% of ${agentsTotal} agents online`,
          },
          icon: "Radio",
          spark: data.agent_health.map((a) => Math.round(a.events_per_sec)),
        },
        {
          kpi: data.monitored_units,
          icon: "Building2",
          spark: data.units.map((u) => u.events),
        },
        {
          kpi: {
            label: "Open Incidents",
            value: openIncidents?.total ?? 0,
            change_pct: null,
            compare_label: "open",
            detail: `${openIncidents?.critical ?? 0} requiring attention`,
            status: openIncidents && openIncidents.critical > 0 ? "critical" : "ok",
          },
          icon: "Siren",
          valueClassName: openIncidents && openIncidents.critical > 0 ? "text-critical" : "text-foreground",
          spark: data.units.map((u) => u.alerts),
        },
      ]
    : [];

  return (
    <div>
      <PageHeader
        title="Command Center"
        description={`Real-time posture across all deployed units and Windows agents · Welcome back, ${user?.full_name?.split(" ")[0] ?? "Analyst"}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success" className="gap-1.5 text-[10px]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              SYSTEM OPERATIONAL
            </Badge>
            <Badge variant="accent" className="text-[10px]">
              {formatCompact(onlineAgents)} AGENTS ONLINE
            </Badge>
            <div className="flex items-center gap-1 rounded-md border border-border bg-surface p-1">
              {PERIODS.map((p) => (
                <Button
                  key={p.key}
                  variant={period === p.key ? "secondary" : "ghost"}
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setPeriod(p.key)}
                >
                  {p.label}
                </Button>
              ))}
            </div>
          </div>
        }
      />

      {isLoading && <PageLoading rows={8} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {kpis.map(({ kpi, icon, spark, valueClassName }) => (
              <KpiCard key={kpi.label} kpi={kpi} icon={icon} spark={spark} valueClassName={valueClassName} />
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <TimelineChart data={data.timeline} />
            </div>
            <SeverityDonut data={data.severity} />
          </div>

          <UnitSecurityMap units={data.units} />

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <ActiveThreats threats={data.active_threats} />
            <LiveEventStream />
            <div className="space-y-4">
              <UnitOverviewTable units={data.units} />
              <AgentHealthTable items={data.agent_health} />
            </div>
          </div>

          <TopRulesTable rules={data.top_rules} />
        </div>
      )}
    </div>
  );
}

function UnitOverviewTable({ units }: { units: { id: string; unit_code: string; name: string; city: string | null; agents: number; events: number; alerts: number; risk: number; status: string }[] }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle>Unit Risk Overview</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Unit</TableHead>
              <TableHead className="text-right">Agents</TableHead>
              <TableHead className="text-right">Events</TableHead>
              <TableHead className="text-right">Alerts</TableHead>
              <TableHead className="text-right">Risk</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {units.slice(0, 8).map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <span className="font-mono text-[12px] text-accent">{u.unit_code}</span>
                  <span className="block text-[11px] text-muted">{u.name}</span>
                </TableCell>
                <TableCell className="text-right font-mono text-xs">{u.agents}</TableCell>
                <TableCell className="text-right font-mono text-xs">{formatCompact(u.events)}</TableCell>
                <TableCell className="text-right font-mono text-xs">{u.alerts}</TableCell>
                <TableCell className="text-right">
                  <span
                    className={cn(
                      "font-mono text-xs font-semibold",
                      u.risk >= 60 ? "text-critical" : u.risk >= 35 ? "text-medium" : "text-emerald-400",
                    )}
                  >
                    {u.risk}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function AgentHealthTable({ items }: { items: { id: string; hostname: string; unit_name: string | null; status: string; events_per_sec: number; cpu_usage: number; memory_usage: number; simulated: boolean }[] }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle>Agent Health</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Host</TableHead>
              <TableHead className="text-right">Events/s</TableHead>
              <TableHead className="text-right">CPU</TableHead>
              <TableHead className="text-right">RAM</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.slice(0, 6).map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <span className="text-xs text-foreground">{a.hostname}</span>
                  <span className="block text-[10px] text-muted">{a.unit_name}</span>
                </TableCell>
                <TableCell className="text-right font-mono text-xs">{a.events_per_sec.toFixed(1)}</TableCell>
                <TableCell className="text-right font-mono text-xs">{a.cpu_usage.toFixed(1)}%</TableCell>
                <TableCell className="text-right font-mono text-xs">{a.memory_usage.toFixed(1)}%</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusBadge status={a.status} className="text-[9px]" />
                      {a.simulated && <Badge variant="outline" className="text-[9px]">simulated</Badge>}
                    </div>
                  </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function TopRulesTable({ rules }: { rules: { rule_id: string; name: string; severity: string; times_matched: number; mitre_technique: string | null }[] }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2">
          Top Detection Rules
          <Badge variant="accent" className="text-[9px]">by matches</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rule</TableHead>
              <TableHead>MITRE</TableHead>
              <TableHead className="text-right">Matches</TableHead>
              <TableHead>Severity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((r) => (
              <TableRow key={r.rule_id}>
                <TableCell>
                  <span className="font-mono text-[12px] text-accent">{r.rule_id}</span>
                  <span className="block text-xs text-foreground">{r.name}</span>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted">{r.mitre_technique ?? "—"}</TableCell>
                <TableCell className="text-right font-mono text-xs">{r.times_matched}</TableCell>
                <TableCell>
                  <SeverityBadge severity={r.severity} className="text-[9px]" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
