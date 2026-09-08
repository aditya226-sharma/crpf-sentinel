"use client";

import { useEffect, useMemo, useState } from "react";
import { Clock3, RefreshCw, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

function useNow(interval = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), interval);
    return () => clearInterval(id);
  }, [interval]);
  return now;
}

interface IstParts {
  hour: number;
  time: string;
  date: string;
  zone: string;
}

function istParts(d: Date): IstParts {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    hourCycle: "h23",
    timeZoneName: "short",
  }).formatToParts(d);
  const map: Record<string, string> = {};
  for (const p of parts) map[p.type] = p.value;
  const hour = Number(map.hour ?? "0");
  return {
    hour,
    time: `${map.hour}:${map.minute}:${map.second}`,
    date: `${map.weekday}, ${map.day} ${map.month}`,
    zone: map.timeZoneName ?? "IST",
  };
}

function shiftFor(hour: number): { name: string; window: string } {
  if (hour >= 6 && hour < 13) return { name: "Alpha", window: "06:00–13:00" };
  if (hour >= 13 && hour < 20) return { name: "Bravo", window: "13:00–20:00" };
  if (hour >= 20 && hour < 23) return { name: "Charlie", window: "20:00–23:00" };
  return { name: "Delta", window: "23:00–06:00" };
}

export function OpsStrip({ generatedAt, refreshIntervalSec = 30 }: { generatedAt?: string; refreshIntervalSec?: number }) {
  const now = useNow();
  const ist = useMemo(() => istParts(now), [now]);
  const shift = shiftFor(ist.hour);

  const secondsAgo = useMemo(() => {
    if (!generatedAt) return null;
    const ms = Date.now() - Date.parse(generatedAt);
    if (Number.isNaN(ms)) return null;
    return Math.max(0, Math.floor(ms / 1000));
  }, [generatedAt, now]);

  const nextRefresh = refreshIntervalSec - (secondsAgo ?? 0);
  const refs = secondsAgo !== null && nextRefresh > 0 ? nextRefresh : null;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-md border border-border bg-surface px-4 py-2.5 shadow-panel">
      <div className="flex items-center gap-2.5">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
        </span>
        <div className="text-[11px] leading-tight">
          <p className="font-semibold uppercase tracking-[0.14em] text-slate-300">Shift {shift.name}</p>
          <p className="font-mono text-[10px] text-muted">{shift.window} IST</p>
        </div>
      </div>

      <span className="hidden h-6 w-px bg-border sm:block" />

      <div className="flex items-center gap-2">
        <Clock3 className="h-3.5 w-3.5 text-accent" />
        <div className="leading-tight">
          <p className="font-mono text-sm font-semibold tabular-nums text-foreground">{ist.time}</p>
          <p className="text-[10px] text-muted">
            {ist.date} · {ist.zone}
          </p>
        </div>
      </div>

      <span className="hidden h-6 w-px bg-border md:block" />

      <div className="flex flex-wrap items-center gap-2">
        <RefreshCw className="h-3 w-3 text-slate-500" />
        <span className="text-[11px] text-muted">
          {secondsAgo === null ? (
            "data awaiting refresh"
          ) : (
            <>
              data as of <span className="font-mono text-slate-300">{secondsAgo}s</span> ago
              {refs !== null && (
                <span className="text-slate-500"> · next refresh in {refs}s</span>
              )}
            </>
          )}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Badge variant="accent" className={cn("gap-1.5 text-[9px]")}>
          <Radio className="h-3 w-3" />
          SOC WATCH
        </Badge>
      </div>
    </div>
  );
}