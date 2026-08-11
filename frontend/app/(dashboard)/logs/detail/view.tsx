"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Copy, Check, FileText } from "lucide-react";
import { logService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { Mono } from "@/components/shared/mono";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { formatDateTime, eventIdLabel } from "@/lib/utils";

export default function LogDetailPage({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["logs", "detail", id],
    queryFn: () => logService.detail(Number(id)),
  });

  const { data: related } = useQuery({
    queryKey: ["logs", "related", id],
    queryFn: () => logService.related(Number(id), 8),
    enabled: !!data,
  });

  function copyRaw() {
    if (!data?.raw_log) return;
    void navigator.clipboard.writeText(data.raw_log);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div>
      <PageHeader
        title={`Event #${id}`}
        description="Normalized Windows Event Log details and forensic context."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/logs">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Explorer
            </Link>
          </Button>
        }
      />

      {isLoading && <PageLoading rows={10} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}

      {data && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="space-y-4 xl:col-span-2">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-accent" />
                  Normalized Event
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                  <DetailRow label="Timestamp" value={formatDateTime(data.timestamp)} mono />
                  <DetailRow label="Event ID" value={`${data.event_id} · ${eventIdLabel(data.event_id)}`} mono />
                  <DetailRow label="Hostname" value={data.hostname ?? "—"} mono />
                  <DetailRow label="Unit" value={data.unit_name ?? "—"} />
                  <DetailRow label="Provider" value={data.provider ?? "—"} />
                  <DetailRow label="Category" value={data.category?.replace("_", " ") ?? "—"} />
                  <DetailRow label="Action" value={data.action ?? "—"} />
                  <DetailRow label="Severity" value={<SeverityBadge severity={data.severity} />} />
                  <DetailRow label="Username" value={data.username ?? "—"} mono />
                  <DetailRow label="Source IP" value={data.source_ip ?? "—"} mono />
                  <DetailRow label="Destination IP" value={data.destination_ip ?? "—"} mono />
                  <DetailRow label="Logon Type" value={data.logon_type ?? "—"} />
                  <DetailRow label="Status Code" value={data.status_code ?? "—"} mono />
                  <DetailRow label="Process" value={data.process_name ?? "—"} mono />
                  <DetailRow label="Parser Version" value={data.parser_version ?? "—"} mono />
                  <DetailRow label="Matched Rule" value={data.matched_rule_id ? <Badge variant="accent" className="text-[9px]">{data.matched_rule_id}</Badge> : "None"} />
                </div>

                {data.command_line && (
                  <div className="mt-4">
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">Command Line</p>
                    <pre className="overflow-x-auto rounded-md border border-border bg-background p-3 font-mono text-[12px] text-foreground">{data.command_line}</pre>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-1">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-accent" />
                  Raw Log Payload
                </CardTitle>
                {data.raw_log && (
                  <Button variant="ghost" size="sm" onClick={copyRaw}>
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                    {copied ? "Copied" : "Copy"}
                  </Button>
                )}
              </CardHeader>
              <CardContent>
                {data.raw_log ? (
                  <pre className="max-h-80 overflow-auto rounded-md border border-border bg-background p-3 font-mono text-[11px] leading-relaxed text-slate-400">{data.raw_log}</pre>
                ) : (
                  <p className="text-xs text-muted">No raw payload retained for this event (retention policy).</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="h-fit">
            <CardHeader className="pb-1">
              <CardTitle>Related Activity (1h window)</CardTitle>
            </CardHeader>
            <CardContent>
              {related && related.length === 0 && <p className="text-xs text-muted">No related events found.</p>}
              <div className="space-y-2">
                {related?.map((e) => (
                  <Link
                    key={e.id}
                    href={`/logs/detail?id=${e.id}`}
                    className="block rounded-md border border-border/60 bg-surface2/40 p-2.5 transition-colors hover:border-accent/40"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] text-accent">{e.event_id}</span>
                      <SeverityBadge severity={e.severity} className="text-[9px]" />
                    </div>
                    <p className="mt-1 truncate text-[11px] text-muted">{e.hostname ?? "—"} · {e.username ?? "—"}</p>
                    <p className="font-mono text-[10px] text-slate-500">{formatDateTime(e.timestamp)}</p>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">{label}</p>
      <div className="mt-0.5 text-sm text-foreground">{mono && typeof value === "string" ? <Mono>{value}</Mono> : value}</div>
    </div>
  );
}
