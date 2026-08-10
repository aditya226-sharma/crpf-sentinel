"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { auditService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageError, PageLoading, PageEmpty } from "@/components/shared/page-states";
import { Pagination } from "@/components/shared/pagination";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime } from "@/lib/utils";
import { useDebounce } from "@/hooks/use-utils";
import { cn } from "@/lib/utils";

const CATEGORIES = ["auth", "users", "units", "agents", "rules", "alerts", "reports", "system"];

export default function AuditLogsPage() {
  const [q, setQ] = useState("");
  const debouncedQ = useDebounce(q, 400);
  const [category, setCategory] = useState("all");
  const [page, setPage] = useState(1);

  const params = useMemo(
    () => ({ q: debouncedQ || undefined, category: category === "all" ? undefined : category, page, page_size: 50 }),
    [debouncedQ, category, page],
  );

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["audit", params],
    queryFn: () => auditService.list(params),
  });

  return (
    <div>
      <PageHeader
        title="Audit Trail"
        description="Immutable record of privileged actions across the CyberRakshak platform."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface p-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search user, action…" className="pl-9" />
        </div>
        <Select value={category} onValueChange={(v) => { setCategory(v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CATEGORIES.map((c) => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && <PageLoading rows={15} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <PageEmpty title="No audit entries found" />}

      {data && data.items.length > 0 && (
        <>
          <div className="rounded-md border border-border bg-surface">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap font-mono text-[11px] text-muted">{formatDateTime(entry.created_at)}</TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground">{entry.username ?? "system"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono text-[10px]">{entry.action}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="accent" className="text-[9px]">{entry.category}</Badge>
                    </TableCell>
                    <TableCell className="max-w-[320px]">
                      <pre className={cn("truncate font-mono text-[10px] text-slate-400")}>
                        {entry.details ? JSON.stringify(entry.details) : "—"}
                      </pre>
                    </TableCell>
                    <TableCell className="font-mono text-[10px] text-muted">{entry.ip_address ?? "—"}</TableCell>
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
