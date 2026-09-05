"use client";

import Link from "next/link";
import { Radar as RadarIcon } from "lucide-react";
import { useLiveStream } from "@/hooks/use-live-stream";
import type { LiveEventItem } from "@/types";
import { formatTime, severityColor, eventIdLabel } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Mono } from "@/components/shared/mono";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { cn } from "@/lib/utils";

function EventRow({ event, index }: { event: LiveEventItem; index: number }) {
  const sc = severityColor(event.severity);
  const eventId = typeof event.event_id === "number" ? event.event_id : Number(event.event_id ?? 0);
  const newest = index === 0;

  return (
    <div
      className={cn(
        "grid grid-cols-[64px_1.2fr_1.4fr_1fr_1.6fr_auto] items-center gap-2 border-b border-border/50 px-3 py-1.5 text-[11px] transition-colors hover:bg-surface2/40 last:border-0",
        newest && "animate-fade-slide-in bg-accent/5",
      )}
    >
      <span className="font-mono text-[10px] text-muted">{formatTime(event.timestamp)}</span>
      <span className="truncate font-mono text-[10px] text-slate-400">{event.unit_name ?? "—"}</span>
      <span className="truncate font-mono text-[11px] text-foreground">{event.hostname ?? "—"}</span>
      <span className="flex items-center gap-1.5">
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", sc.dot)} />
        <Mono className={cn("text-[11px]", sc.text)}>{eventId}</Mono>
      </span>
      <span className="truncate text-[11px] text-slate-300">
        {eventIdLabel(eventId)}
        {event.matched_rule_id && (
          <span className="ml-1.5 text-accent">· {event.matched_rule_id}</span>
        )}
      </span>
      <span className="flex shrink-0 items-center gap-1.5">
        {event.simulated && (
          <Badge variant="outline" className="text-[8px]">simulated</Badge>
        )}
        <SeverityBadge severity={event.severity} className="text-[8px]" />
      </span>
    </div>
  );
}

export function LiveEventStream() {
  const { events, connection } = useLiveStream();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-1">
        <CardTitle className="flex items-center gap-2">
          <RadarIcon className="h-4 w-4 text-accent" />
          Live Security Events
        </CardTitle>
        <Badge variant={connection === "live" ? "success" : "medium"} className="text-[9px]">
          <span className="relative flex h-1.5 w-1.5">
            {connection === "live" && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            )}
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
          </span>
          {connection === "live" ? "LIVE" : connection.toUpperCase()}
        </Badge>
      </CardHeader>
      <CardContent className="p-0">
        <div className="grid grid-cols-[64px_1.2fr_1.4fr_1fr_1.6fr_auto] items-center gap-2 border-b border-border bg-surface3 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">
          <span>Time</span>
          <span>Unit</span>
          <span>Host</span>
          <span>Event</span>
          <span>Action</span>
          <span>Severity</span>
        </div>
        {events.length === 0 ? (
          <div className="flex h-56 items-center justify-center">
            <p className="text-xs text-muted">Waiting for incoming events…</p>
          </div>
        ) : (
          <ScrollArea className="h-56">
            <div>
              {events.slice(0, 40).map((event, i) => (
                <EventRow key={`${event.id ?? event.timestamp}-${i}`} event={event} index={i} />
              ))}
            </div>
          </ScrollArea>
        )}
        <div className="border-t border-border px-3 py-2 text-right">
          <Link href="/logs" className="text-[11px] text-accent hover:underline">
            Open log explorer →
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
