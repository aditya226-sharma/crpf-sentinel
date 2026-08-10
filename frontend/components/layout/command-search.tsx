"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { FileSearch, Bell, Siren, ShieldAlert, Network, Building2, Crosshair, Search, Loader2 } from "lucide-react";
import { searchService } from "@/services";
import { useDebounce } from "@/hooks/use-utils";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface Group {
  key: string;
  label: string;
  icon: typeof FileSearch;
  items: { id: string; title: string; sub: string; href: string }[];
}

export function CommandSearch({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const debounced = useDebounce(query, 250);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (open) setQuery("");
  }, [open]);
  const enabled = open && debounced.trim().length > 0;
  const { data, isFetching } = useQuery({
    queryKey: ["command-search", debounced],
    queryFn: () => searchService.all(debounced.trim()),
    enabled,
  });

  const groups = useMemo<Group[]>(() => {
    if (!data) return [];
    const g: Group[] = [];
    if (data.events?.length)
      g.push({
        key: "events", label: "Logs", icon: FileSearch,
        items: data.events.slice(0, 5).map((e) => ({
          id: String(e.id), title: `${e.event_id} · ${e.category ?? "Event"}`,
          sub: `${e.hostname ?? "—"} · ${e.source_ip ?? "—"} · ${e.severity}`,
          href: `/logs/${e.id}`,
        })),
      });
    if (data.alerts?.length)
      g.push({
        key: "alerts", label: "Alerts", icon: Bell,
        items: data.alerts.slice(0, 5).map((a) => ({
          id: a.id, title: a.title, sub: `${a.alert_id} · ${a.hostname ?? "—"} · ${a.status}`,
          href: `/alerts/${a.alert_id}`,
        })),
      });
    if (data.incidents?.length)
      g.push({
        key: "incidents", label: "Incidents", icon: Siren,
        items: data.incidents.slice(0, 5).map((c) => ({
          id: c.id, title: c.title, sub: `${c.incident_id} · ${c.status}`,
          href: `/incidents/${c.id}`,
        })),
      });
    if (data.rules?.length)
      g.push({
        key: "rules", label: "Detection Rules", icon: ShieldAlert,
        items: data.rules.slice(0, 5).map((r) => ({
          id: r.id, title: r.name, sub: `${r.rule_id} · ${r.severity}`,
          href: `/rules?focus=${r.id}`,
        })),
      });
    if (data.agents?.length)
      g.push({
        key: "agents", label: "Windows Agents", icon: Network,
        items: data.agents.slice(0, 5).map((a) => ({
          id: a.id, title: a.hostname ?? a.agent_id, sub: `${a.agent_id} · ${a.ip_address ?? "—"} · ${a.status}`,
          href: `/agents/${a.agent_id}`,
        })),
      });
    if (data.units?.length)
      g.push({
        key: "units", label: "CRPF Units", icon: Building2,
        items: data.units.slice(0, 5).map((u) => ({
          id: u.id, title: u.name, sub: `${u.unit_code} · ${u.status}`,
          href: `/units/${u.id}`,
        })),
      });
    if (data.iocs?.length)
      g.push({
        key: "iocs", label: "IOC Library", icon: Crosshair,
        items: data.iocs.slice(0, 5).map((i) => ({
          id: i.id, title: i.value, sub: `${i.ioc_type} · ${i.severity}`,
          href: "/ioc-library",
        })),
      });
    return g;
  }, [data]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[12%] max-w-xl translate-y-0 gap-0 bg-surface p-0">
        <DialogTitle className="sr-only">Global search</DialogTitle>
        <div className="flex items-center gap-2 border-b border-border px-4">
          <Search className="h-4 w-4 shrink-0 text-muted" />
          <Input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search logs, alerts, agents, units, rules, IPs, hostnames…"
            className="h-12 border-0 bg-transparent text-sm shadow-none focus-visible:ring-0"
            onKeyDown={(e) => {
              if (e.key === "Enter" && groups.length > 0 && groups[0].items.length > 0) {
                router.push(groups[0].items[0].href);
                onOpenChange(false);
              }
            }}
          />
          <Badge variant="default" className="hidden text-[9px] sm:inline-flex">ESC</Badge>
        </div>
        <div className="max-h-[420px] overflow-y-auto p-2">
          {isFetching && (
            <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Searching…
            </div>
          )}
          {!isFetching && query.trim() && groups.length === 0 && (
            <div className="py-8 text-center text-xs text-muted">No results for “{query}”</div>
          )}
          {!query.trim() && (
            <div className="px-3 py-6 text-center text-[11px] text-muted">
              Search across logs, alerts, incidents, agents, units, rules and IOCs.
            </div>
          )}
          {groups.map((group) => (
            <div key={group.key} className="mb-1">
              <div className="flex items-center gap-1.5 px-3 py-1.5">
                <group.icon className="h-3 w-3 text-muted" />
                <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted">
                  {group.label}
                </span>
              </div>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    router.push(item.href);
                    onOpenChange(false);
                  }}
                  className="flex w-full flex-col items-start rounded-md px-3 py-2 text-left transition-colors hover:bg-surface2"
                >
                  <span className="text-[13px] text-foreground">{item.title}</span>
                  <span className="font-mono text-[10px] text-muted">{item.sub}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[10px] text-muted">
          <span className="flex items-center gap-1"><kbd className="rounded border border-border bg-surface2 px-1 font-mono">↑↓</kbd> Navigate</span>
          <span className="flex items-center gap-1"><kbd className="rounded border border-border bg-surface2 px-1 font-mono">↵</kbd> Open</span>
          <span className="ml-auto text-muted/70">CyberRakshak · Global Search</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function SearchButton({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className={cn(
        "hidden w-64 items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-left transition-colors hover:border-slate-600 md:flex",
      )}
      aria-label="Open global search"
    >
      <Search className="h-3.5 w-3.5 text-muted" />
      <span className="flex-1 truncate text-[12px] text-muted">Search hostname, IP, event ID, alert…</span>
      <kbd className="rounded border border-border bg-surface2 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
        ⌘K
      </kbd>
    </button>
  );
}
