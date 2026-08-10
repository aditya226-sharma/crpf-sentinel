"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search, Filter, RotateCcw, Download } from "lucide-react";
import { logService, type LogFilters } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { PageError, PageLoading, PageEmpty } from "@/components/shared/page-states";
import { Pagination } from "@/components/shared/pagination";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, eventIdLabel, downloadText, cn } from "@/lib/utils";
import { useDebounce } from "@/hooks/use-utils";

const CATEGORIES = ["authentication", "process_creation", "account_management", "service_installation", "security_audit", "credential_usage", "privilege_assignment", "unknown"];
const SEVERITIES = ["critical", "high", "medium", "low", "informational"];

export default function LogsPage() {
  const [q, setQ] = useState("");
  const debouncedQ = useDebounce(q, 400);
  const [severity, setSeverity] = useState<string>("all");
  const [category, setCategory] = useState<string>("all");
  const [eventId, setEventId] = useState("");
  const [hostname, setHostname] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<"asc" | "desc">("desc");

  const filters = useMemo<LogFilters>(
    () => ({
      q: debouncedQ || undefined,
      severity: severity === "all" ? undefined : severity,
      category: category === "all" ? undefined : category,
      event_id: eventId ? Number(eventId) : undefined,
      hostname: hostname || undefined,
      page,
      page_size: 25,
      sort,
    }),
    [debouncedQ, severity, category, eventId, hostname, page, sort],
  );

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["logs", filters],
    queryFn: () => logService.list(filters),
    placeholderData: (prev) => prev,
  });

  function resetFilters() {
    setQ("");
    setSeverity("all");
    setCategory("all");
    setEventId("");
    setHostname("");
    setPage(1);
  }

  function exportCsv() {
    if (!data) return;
    const header = "id,timestamp,unit,hostname,event_id,category,action,severity,username,source_ip,is_suspicious";
    const rows = data.items.map((e) =>
      [e.id, e.timestamp, e.unit_name ?? "", e.hostname ?? "", e.event_id, e.category ?? "", e.action ?? "", e.severity, e.username ?? "", e.source_ip ?? "", e.is_suspicious]
        .map((v) => {
          const s = String(v);
          const escaped = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
          return `"${escaped.replace(/"/g, '""')}"`;
        })
        .join(","),
    );
    downloadText(`cyberrakshak-events-${new Date().toISOString().slice(0, 10)}.csv`, [header, ...rows].join("\n"), "text/csv");
  }

  return (
    <div>
      <PageHeader
        title="Log Explorer"
        description="Search normalized Windows Event Logs across all units and agents."
        actions={
          <Button variant="outline" size="sm" onClick={exportCsv} disabled={!data?.items.length}>
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface p-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search hostname, user, IP, action…" className="pl-9" />
        </div>
        <Select value={severity} onValueChange={(v) => { setSeverity(v); setPage(1); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            {SEVERITIES.map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={category} onValueChange={(v) => { setCategory(v); setPage(1); }}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CATEGORIES.map((c) => (
              <SelectItem key={c} value={c}>{c.replace("_", " ")}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input value={eventId} onChange={(e) => { setEventId(e.target.value); setPage(1); }} placeholder="Event ID (4624)" className="w-32 font-mono" />
        <Input value={hostname} onChange={(e) => { setHostname(e.target.value); setPage(1); }} placeholder="Hostname" className="w-40" />
        <Button variant="outline" size="icon" onClick={() => setSort((s) => (s === "desc" ? "asc" : "desc"))} aria-label="Toggle sort" title={`Sorted ${sort}`}>
          <Filter className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={resetFilters} aria-label="Reset filters">
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      {isLoading && <PageLoading rows={15} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <PageEmpty title="No events match your filters" />}

      {data && data.items.length > 0 && (
        <>
          <div className={cn("rounded-md border border-border bg-surface", isFetching && "opacity-60")}>
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
                  <TableHead>Rule</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="whitespace-nowrap font-mono text-[11px] text-muted">
                      <Link href={`/logs/${e.id}`} className="hover:text-accent">{formatDateTime(e.timestamp)}</Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/logs/${e.id}`} className="hover:text-accent">
                        <span className="text-xs text-foreground">{e.hostname ?? "—"}</span>
                        <span className="block text-[10px] text-muted">{e.unit_name}</span>
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/logs/${e.id}`} className="hover:text-accent">
                        <span className="font-mono text-[12px] text-accent">{e.event_id}</span>
                        <span className="block text-[10px] text-muted">{eventIdLabel(e.event_id)}</span>
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs text-muted">{e.category?.replace("_", " ") ?? "—"}</TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground">{e.username ?? "—"}</TableCell>
                    <TableCell className="font-mono text-[11px] text-muted">{e.source_ip ?? "—"}</TableCell>
                    <TableCell><SeverityBadge severity={e.severity} className="text-[9px]" /></TableCell>
                    <TableCell>
                      {e.matched_rule_id ? (
                        <Badge variant="accent" className="text-[9px]">{e.matched_rule_id}</Badge>
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </TableCell>
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
