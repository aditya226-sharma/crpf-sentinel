"use client";

import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimelinePoint } from "@/types";
import { formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function bucketLabel(bucket: string, previousDay: string | null): string {
  const [datePart, hourPart] = bucket.split(" ");
  if (!hourPart) return bucket;
  const label = `${hourPart.padStart(2, "0")}:00`;
  return previousDay && datePart !== previousDay ? `${datePart.slice(5)} ${label}` : label;
}

function absTime(bucket: string): string {
  const [datePart, hourPart] = bucket.split(" ");
  if (!hourPart) return bucket;
  return `${datePart} ${hourPart.padStart(2, "0")}:00`;
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-surface2 px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-mono text-foreground">
        {absTime(String(label))} <span className="text-slate-500">IST</span>
      </p>
      {payload.map((entry: any) => (
        <p key={entry.dataKey} className="flex items-center gap-2 text-muted">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: entry.color }} />
          {entry.name}: <span className="font-mono text-foreground">{formatNumber(entry.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function TimelineChart({ data, period = "24h" }: { data: TimelinePoint[]; period?: string }) {
  const { rows, peak, lastBucket } = useMemo(() => {
    let previousDay: string | null = null;
    const rows = data.map((d) => {
      const [datePart] = d.bucket.split(" ");
      const label = bucketLabel(d.bucket, previousDay);
      previousDay = datePart;
      return { ...d, label, full: absTime(d.bucket) };
    });
    let peak: { events: number; label: string } | null = null;
    for (const r of rows) {
      if (!peak || r.events > peak.events) peak = { events: r.events, label: r.label };
    }
    return { rows, peak, lastBucket: rows.length > 0 ? rows[rows.length - 1].label : undefined };
  }, [data]);

  if (rows.length < 2) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">Event & Alert Volume</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
            <p className="text-xs text-muted">Not enough data in this window yet.</p>
            <p className="text-[11px] text-muted/70">Run a demo scenario or wait for the next seed to populate the timeline.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="shadow-panel">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2">
          Event & Alert Volume
          <Badge variant="accent" className="text-[9px]">
            {period.toUpperCase()} · HOURLY
          </Badge>
        </CardTitle>
        {peak && (
          <span className="text-[10px] text-muted">
            peak <span className="font-mono text-slate-300">{formatNumber(peak.events)}</span> events at{" "}
            <span className="font-mono text-slate-300">{peak.label}</span>
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="eventsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#22D3EE" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="alertsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#EF4444" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#EF4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1E293B" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                stroke="#475569"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                interval={Math.max(1, Math.floor(rows.length / 8))}
              />
              <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              {lastBucket && <ReferenceLine x={lastBucket} stroke="#22D3EE" strokeDasharray="3 3" strokeOpacity={0.5} />}
              <Area
                type="monotone"
                dataKey="events"
                name="Events"
                stroke="#22D3EE"
                strokeWidth={1.5}
                fill="url(#eventsGrad)"
              />
              <Area
                type="monotone"
                dataKey="alerts"
                name="Alerts"
                stroke="#EF4444"
                strokeWidth={1.5}
                fill="url(#alertsGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}