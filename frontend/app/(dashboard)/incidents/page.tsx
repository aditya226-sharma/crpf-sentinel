"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Siren } from "lucide-react";
import { incidentService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { PageError, PageLoading, PageEmpty } from "@/components/shared/page-states";
import { Pagination } from "@/components/shared/pagination";
import { Mono } from "@/components/shared/mono";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { timeAgo, severityColor } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

const STATUSES = ["triaging", "investigating", "escalated", "resolved", "closed"];
const SEVERITIES = ["critical", "high", "medium", "low"];

export default function IncidentsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [page, setPage] = useState(1);

  const params = useMemo(
    () => ({
      status: status === "all" ? undefined : status,
      severity: severity === "all" ? undefined : severity,
      page,
      page_size: 25,
    }),
    [status, severity, page],
  );

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["incidents", params],
    queryFn: () => incidentService.list(params),
  });

  return (
    <div>
      <PageHeader
        title="Incidents"
        description="Case management: triage, investigate, escalate, resolve and close security incidents."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void refetch();
              void queryClient.invalidateQueries({ queryKey: ["incidents"] });
            }}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface p-3">
        <Siren className="h-4 w-4 text-muted" />
        <Select value={status} onValueChange={(v) => { setStatus(v); setPage(1); }}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={severity} onValueChange={(v) => { setSeverity(v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            {SEVERITIES.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && <PageLoading rows={15} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <PageEmpty title="No incidents in this view" />}

      {data && data.items.length > 0 && (
        <>
          <div className="rounded-md border border-border bg-surface">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Incident</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Host</TableHead>
                  <TableHead>Alerts</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Last activity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((inc) => (
                  <TableRow key={inc.id}>
                    <TableCell>
                      <Link href={`/incidents/detail?id=${inc.id}`} className="group block min-w-0">
                        <span className="block truncate text-sm font-medium text-foreground group-hover:text-accent">
                          {inc.title}
                        </span>
                        <span className="block font-mono text-[11px] text-muted">
                          {inc.incident_id} · {inc.unit_name ?? "—"}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <SeverityBadge severity={inc.severity} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={inc.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">{inc.hostname ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{inc.alert_count}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={inc.risk_score} className="h-1.5 w-16" colorClass={severityColor(inc.severity).bg} />
                        <Mono>{inc.risk_score}</Mono>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted">{timeAgo(inc.last_seen)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} totalPages={data.meta.total_pages} total={data.meta.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
