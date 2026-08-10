"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Cpu, HardDrive, MemoryStick, Radio } from "lucide-react";
import { agentService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { Mono } from "@/components/shared/mono";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { formatDateTime, timeAgo } from "@/lib/utils";

export default function AgentDetailPage({ id }: { id: string }) {

  const agentQuery = useQuery({
    queryKey: ["agents", "detail", id],
    queryFn: () => agentService.detail(id),
    refetchInterval: 15000,
  });

  const eventsQuery = useQuery({
    queryKey: ["agents", "events", id],
    queryFn: () => agentService.events(id),
    refetchInterval: 15000,
  });

  const agent = agentQuery.data;
  const loading = agentQuery.isLoading;
  const error = agentQuery.error as Error | null;

  return (
    <div>
      <PageHeader
        title="Agent Detail"
        description={agent ? `${agent.agent_id} · ${agent.hostname}` : "Loading…"}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/agents">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Agents
            </Link>
          </Button>
        }
      />

      {loading && <PageLoading rows={8} />}
      {error && <PageError message={error.message} onRetry={() => agentQuery.refetch()} />}

      {agent && (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-mono text-sm font-semibold text-foreground">{agent.agent_id}</p>
                    <p className="mt-1 text-xs text-muted">{agent.hostname}</p>
                  </div>
                  <StatusBadge status={agent.status} />
                </div>
                <dl className="mt-4 space-y-2 text-xs">
                  <Row label="Unit" value={agent.unit_name ?? "—"} mono />
                  <Row label="IP address" value={agent.ip_address ?? "—"} mono />
                  <Row label="OS" value={agent.os_version ?? "—"} />
                  <Row label="Agent version" value={agent.agent_version ?? "—"} mono />
                  <Row label="Last seen" value={agent.last_seen_at ? timeAgo(agent.last_seen_at) : "—"} />
                  <Row label="Sync status" value={agent.last_sync_status ?? "—"} mono />
                  <Row label="Buffer size" value={agent.buffer_size != null ? `${agent.buffer_size} events` : "—"} />
                </dl>
                <div className="mt-4 flex items-center gap-2">
                  <Badge variant={agent.is_enabled ? "success" : "default"} className="text-[9px]">
                    {agent.is_enabled ? "ENABLED" : "DISABLED"}
                  </Badge>
                  <Badge variant="outline" className="font-mono text-[9px]">
                    registered {agent.created_at ? timeAgo(agent.created_at) : "—"}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
              <MetricCard icon={Radio} label="Events / second" value={agent.events_per_sec} />
              <MetricCard icon={Cpu} label="CPU usage" value={`${agent.cpu_usage}%`} pct={agent.cpu_usage} />
              <MetricCard icon={MemoryStick} label="Memory usage" value={`${agent.memory_usage}%`} pct={agent.memory_usage} />
              <MetricCard icon={HardDrive} label="Spool buffer" value={agent.buffer_size != null ? `${agent.buffer_size} events` : "—"} />
            </div>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Recent Events</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-96 overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Event</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>User / Source</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Rule</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {eventsQuery.data?.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-8 text-center text-xs text-muted">No events from this agent yet.</TableCell>
                      </TableRow>
                    )}
                    {eventsQuery.data?.map((ev) => (
                      <TableRow key={ev.id}>
                        <TableCell className="whitespace-nowrap text-xs text-muted">{formatDateTime(ev.timestamp)}</TableCell>
                        <TableCell><Mono>{ev.event_id}</Mono></TableCell>
                        <TableCell className="text-xs">{ev.category ?? "—"}</TableCell>
                        <TableCell className="text-xs">
                          {ev.username ?? "—"}
                          {ev.source_ip && <span className="font-mono text-muted"> · {ev.source_ip}</span>}
                        </TableCell>
                        <TableCell><SeverityBadge severity={ev.severity} /></TableCell>
                        <TableCell className="text-xs">
                          {ev.matched_rule_id ? <Mono>{ev.matched_rule_id}</Mono> : <span className="text-muted">—</span>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted">{label}</dt>
      <dd className={mono ? "font-mono text-foreground" : "text-right text-foreground"}>{value}</dd>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  pct,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  pct?: number;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-muted">
          <Icon className="h-4 w-4 text-accent" />
          <span className="text-xs">{label}</span>
        </div>
        <p className="mt-2 font-mono text-2xl font-semibold text-foreground">{value}</p>
        {pct !== undefined && <Progress value={pct} className="mt-2 h-1.5" />}
      </CardContent>
    </Card>
  );
}
