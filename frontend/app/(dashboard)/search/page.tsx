"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search as SearchIcon, FileSearch, Bell, Siren, ShieldAlert, Crosshair, Network, Building2, X } from "lucide-react";
import { searchService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { Mono } from "@/components/shared/mono";

const MIN_QUERY = 2;

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 400);
    return () => clearTimeout(t);
  }, [q]);

  const enabled = debounced.length >= MIN_QUERY;
  const { data, isLoading, isError } = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => searchService.all(debounced),
    enabled,
    placeholderData: (prev) => prev,
  });

  const total = data
    ? data.events.length + data.alerts.length + data.incidents.length + data.rules.length + data.iocs.length + data.agents.length + data.units.length
    : 0;

  return (
    <div>
      <PageHeader
        title="Global Search"
        description="Search across events, alerts, incidents, rules, IOCs, agents and units."
      />

      <div className="relative mb-6 max-w-2xl">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search hostname, IP, username, event, alert, rule, IOC, incident…"
          className="h-11 pl-9 pr-9 font-mono text-sm"
        />
        {q && (
          <button
            onClick={() => setQ("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {enabled && isError && <p className="text-xs text-critical">Search failed. Try again.</p>}
      {!enabled && <p className="text-xs text-muted">Type at least {MIN_QUERY} characters to search.</p>}
      {enabled && !isLoading && data && (
        <p className="mb-4 text-xs text-muted">{total} result{total === 1 ? "" : "s"} for <span className="font-mono text-foreground">“{debounced}”</span></p>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        <ResultCard icon={FileSearch} title="Events" count={data?.events.length ?? 0} color="text-accent">
          {(data?.events ?? []).map((e) => (
            <ResultRow key={e.id} href={`/logs/detail?id=${e.id}`} title={`${e.event_id} · ${e.hostname ?? "—"}`} sub={`${e.username ?? "—"} · ${e.source_ip ?? "—"}`} right={<SeverityBadge severity={e.severity} />} meta={`${e.category ?? ""}`} />
          ))}
        </ResultCard>

        <ResultCard icon={Bell} title="Alerts" count={data?.alerts.length ?? 0} color="text-orange-400">
          {(data?.alerts ?? []).map((a) => (
            <ResultRow key={a.id} href={`/alerts/detail?id=${a.id}`} title={a.title} sub={a.alert_id} right={<SeverityBadge severity={a.severity} />} meta={<StatusBadge status={a.status} />} />
          ))}
        </ResultCard>

        <ResultCard icon={Siren} title="Incidents" count={data?.incidents.length ?? 0} color="text-red-400">
          {(data?.incidents ?? []).map((i) => (
            <ResultRow key={i.id} href={`/incidents/detail?id=${i.id}`} title={i.title} sub={i.incident_id} right={<SeverityBadge severity={i.severity} />} meta={<StatusBadge status={i.status} />} />
          ))}
        </ResultCard>

        <ResultCard icon={ShieldAlert} title="Rules" count={data?.rules.length ?? 0} color="text-emerald-400">
          {(data?.rules ?? []).map((r) => (
            <ResultRow key={r.id} href="/rules" title={r.name} sub={r.rule_id} right={<SeverityBadge severity={r.severity} />} meta={`${r.times_matched} matches`} />
          ))}
        </ResultCard>

        <ResultCard icon={Crosshair} title="IOCs" count={data?.iocs.length ?? 0} color="text-cyan-400">
          {(data?.iocs ?? []).map((i) => (
            <ResultRow key={i.id} href="/ioc-library" title={i.value} sub={i.ioc_id} right={<Mono>{i.ioc_type}</Mono>} meta={<SeverityBadge severity={i.severity} />} />
          ))}
        </ResultCard>

        <div className="grid gap-4">
          <ResultCard icon={Network} title="Agents" count={data?.agents.length ?? 0} color="text-blue-400">
            {(data?.agents ?? []).map((a) => (
              <ResultRow key={a.id} href={`/agents/detail?id=${a.id}`} title={a.hostname} sub={a.agent_id} right={<StatusBadge status={a.status} />} meta={a.ip_address} />
            ))}
          </ResultCard>
          <ResultCard icon={Building2} title="Units" count={data?.units.length ?? 0} color="text-violet-400">
            {(data?.units ?? []).map((u) => (
              <ResultRow key={u.id} href={`/units/detail?id=${u.id}`} title={u.name} sub={u.unit_code} right={<StatusBadge status={u.status} />} />
            ))}
          </ResultCard>
        </div>
      </div>
    </div>
  );
}

function ResultCard({
  icon: Icon,
  title,
  count,
  color,
  children,
}: {
  icon: React.ElementType;
  title: string;
  count: number;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2">
            <Icon className={`h-4 w-4 ${color}`} />
            {title}
          </span>
          <span className="font-mono text-xs text-muted">{count}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {count === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-muted">No matches</p>
        ) : (
          <div className="divide-y divide-border/60">{children}</div>
        )}
      </CardContent>
    </Card>
  );
}

function ResultRow({
  href,
  title,
  sub,
  meta,
  right,
}: {
  href: string;
  title: string;
  sub?: React.ReactNode;
  meta?: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <Link href={href} className="group block px-4 py-2.5 hover:bg-surface">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-foreground group-hover:text-accent">{title}</p>
          {sub && <p className="truncate font-mono text-[10px] text-muted">{sub}</p>}
          {meta && <p className="mt-0.5 truncate text-[10px] text-muted">{meta}</p>}
        </div>
        <div className="shrink-0">{right}</div>
      </div>
    </Link>
  );
}
