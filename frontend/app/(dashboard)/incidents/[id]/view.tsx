"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  Flame,
  Siren,
  AlertOctagon,
  Stethoscope,
  ShieldCheck,
  Plus,
} from "lucide-react";
import { incidentService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { MitreBadge } from "@/components/shared/mitre-badge";
import { Mono } from "@/components/shared/mono";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, severityColor, timeAgo } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

const STATUS_ACTIONS = [
  { status: "investigating", label: "Start Investigation", icon: Stethoscope, variant: "outline" as const },
  { status: "escalated", label: "Escalate", icon: AlertOctagon, variant: "outline" as const },
  { status: "resolved", label: "Resolve", icon: CheckCircle2, variant: "default" as const },
  { status: "closed", label: "Close", icon: ShieldCheck, variant: "ghost" as const },
];

export default function IncidentDetailPage({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [transitioning, setTransitioning] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["incidents", "detail", id],
    queryFn: () => incidentService.detail(id),
    refetchInterval: 30000,
  });

  async function transition(status: string) {
    setTransitioning(status);
    try {
      await incidentService.update(id, { status });
      await queryClient.invalidateQueries({ queryKey: ["incidents"] });
      void refetch();
    } finally {
      setTransitioning(null);
    }
  }

  async function addNote() {
    if (!note.trim()) return;
    setSavingNote(true);
    try {
      await incidentService.addNote(id, note.trim());
      setNote("");
      void refetch();
    } finally {
      setSavingNote(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Incident Detail"
        description={data ? `${data.incident_id} · Case Management` : "Loading…"}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/incidents">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Incidents
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
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={data.severity} />
                    <StatusBadge status={data.status} />
                    <Badge variant="outline" className="font-mono text-[9px]">{data.incident_id}</Badge>
                    {data.category && <Badge variant="info" className="text-[10px]">{data.category}</Badge>}
                  </div>
                  <h2 className="mt-2 text-lg font-semibold text-foreground">{data.title}</h2>
                  <p className="mt-1 max-w-3xl text-sm text-muted">{data.description}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted">
                    <span>Host: <span className="font-mono text-foreground">{data.hostname ?? "—"}</span></span>
                    <span>Source: <span className="font-mono text-foreground">{data.source_ip ?? "—"}</span></span>
                    <span>User: <span className="font-mono text-foreground">{data.username ?? "—"}</span></span>
                    <span>Unit: <span className="font-mono text-foreground">{data.unit_name ?? "—"}</span></span>
                    <span>MITRE: <MitreBadge technique={data.mitre_technique} name={data.mitre_name} /></span>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <div className="flex items-center gap-2">
                    <Progress value={data.risk_score} colorClass={severityColor(data.severity).bg} className="h-2 w-40" />
                    <span className="font-mono text-lg font-semibold text-foreground">{data.risk_score}</span>
                  </div>
                  <span className="text-[10px] uppercase tracking-widest text-muted">Risk Score</span>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
                {STATUS_ACTIONS.map((action) => {
                  const Icon = action.icon;
                  return (
                    <Button
                      key={action.status}
                      variant={action.variant}
                      size="sm"
                      disabled={transitioning !== null || data.status === action.status}
                      onClick={() => transition(action.status)}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {transitioning === action.status ? "Updating…" : action.label}
                    </Button>
                  );
                })}
                <span className="ml-auto text-xs text-muted">
                  Updated {timeAgo(data.updated_at)} · {data.alert_count} alerts · {data.event_count} events
                </span>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Siren className="h-4 w-4 text-accent" />
                  Linked Alerts
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {data.alerts.length === 0 ? (
                  <p className="px-4 py-8 text-center text-xs text-muted">No linked alerts.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Alert</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Events</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.alerts.map((alert) => (
                        <TableRow key={alert.id}>
                          <TableCell>
                            <Link href={`/alerts/${alert.id}`} className="group block min-w-0">
                              <span className="block truncate text-sm font-medium text-foreground group-hover:text-accent">{alert.title}</span>
                              <span className="block font-mono text-[11px] text-muted">{alert.alert_id} · {alert.hostname ?? "—"}</span>
                            </Link>
                          </TableCell>
                          <TableCell><SeverityBadge severity={alert.severity} /></TableCell>
                          <TableCell><StatusBadge status={alert.status} /></TableCell>
                          <TableCell className="font-mono text-xs">{alert.event_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Stethoscope className="h-4 w-4 text-accent" />
                  Investigation Notes
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="mb-4 flex gap-2">
                  <Textarea
                    rows={2}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Add an investigation note…"
                    className="resize-none text-xs"
                  />
                  <Button size="sm" variant="outline" className="shrink-0 self-end" disabled={!note.trim() || savingNote} onClick={addNote}>
                    <Plus className="h-3.5 w-3.5" />
                    Add
                  </Button>
                </div>
                <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
                  {data.notes.length === 0 && (
                    <p className="py-4 text-center text-xs text-muted">No notes yet.</p>
                  )}
                  {data.notes.map((n) => (
                    <div key={n.id} className="rounded-md border border-border/60 bg-surface p-3">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-foreground">{n.username}</span>
                        <span className="text-[10px] text-muted">{formatDateTime(n.timestamp)}</span>
                      </div>
                      <p className="whitespace-pre-wrap text-xs text-muted">{n.content}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Flame className="h-4 w-4 text-accent" />
                Event Timeline
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-96 overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Host</TableHead>
                      <TableHead>Event</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>User / Source</TableHead>
                      <TableHead>Severity</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <IncidentEvents id={id} />
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

function IncidentEvents({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["incidents", "events", id],
    queryFn: () => incidentService.events(id),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <TableRow>
        <TableCell colSpan={6} className="py-8 text-center text-xs text-muted">Loading events…</TableCell>
      </TableRow>
    );
  }
  if (isError) {
    return (
      <TableRow>
        <TableCell colSpan={6} className="py-8 text-center text-xs text-critical">Failed to load events.</TableCell>
      </TableRow>
    );
  }
  if (!data || data.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={6} className="py-8 text-center text-xs text-muted">No linked events.</TableCell>
      </TableRow>
    );
  }
  return (
    <>
      {data.map((ev) => (
        <TableRow key={ev.id}>
          <TableCell className="whitespace-nowrap text-xs text-muted">{formatDateTime(ev.timestamp)}</TableCell>
          <TableCell className="font-mono text-xs">{ev.hostname ?? "—"}</TableCell>
          <TableCell><Mono>{ev.event_id}</Mono></TableCell>
          <TableCell className="text-xs">{ev.action ?? ev.category ?? "—"}</TableCell>
          <TableCell className="text-xs">
            {ev.username ?? "—"}
            {ev.source_ip && <span className="font-mono text-muted"> · {ev.source_ip}</span>}
          </TableCell>
          <TableCell><SeverityBadge severity={ev.severity} /></TableCell>
        </TableRow>
      ))}
    </>
  );
}
