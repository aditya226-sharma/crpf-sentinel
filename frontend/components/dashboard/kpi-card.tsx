import type { KpiValue } from "@/types";
import { formatNumber, cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Database, ShieldAlert, BellRing, Radio, Building2, Gauge, Siren, type LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  Database,
  ShieldAlert,
  BellRing,
  Radio,
  Building2,
  Gauge,
  Siren,
};

type Tone = "neutral" | "ok" | "warn" | "critical";

const TONE_BAR: Record<Tone, string> = {
  neutral: "from-cyan-400/70 via-cyan-400/20 to-transparent",
  ok: "from-emerald-400/80 via-emerald-400/20 to-transparent",
  warn: "from-amber-400/80 via-amber-400/20 to-transparent",
  critical: "from-red-400/90 via-red-400/25 to-transparent",
};

function Sparkline({ points, className }: { points: number[]; className?: string }) {
  if (points.length === 0) return <div className="h-6" />;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = max - min || 1;
  const allFlat = max === min;
  const step = 100 / Math.max(points.length - 1, 1);
  const coords = allFlat
    ? `0,28 ${points.length > 1 ? "50,28" : "100,28"} 100,28`
    : points
        .map((p, i) => `${(i * step).toFixed(1)},${(34 - ((p - min) / range) * 26).toFixed(1)}`)
        .join(" ");
  return (
    <svg viewBox="0 0 100 36" preserveAspectRatio="none" className={cn("h-6 w-full", className)} aria-hidden>
      <polyline
        points={coords}
        fill="none"
        stroke={allFlat ? "currentColor" : "currentColor"}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        strokeDasharray={allFlat ? "3 3" : undefined}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function DeltaChip({ pct }: { pct: number | null }) {
  if (pct === null || pct === undefined) {
    return (
      <span className="rounded border border-border px-1 py-px font-mono text-[10px] text-slate-500" title="no prior-period comparison">
        n/a
      </span>
    );
  }
  const spike = Math.abs(pct) > 500;
  if (spike) {
    return (
      <span
        className="rounded border border-amber-500/30 bg-amber-500/10 px-1 py-px font-mono text-[10px] text-amber-400"
        title="no meaningful prior-period baseline"
      >
        {pct >= 0 ? "▲" : "▼"} fresh
      </span>
    );
  }
  const up = pct >= 0;
  return (
    <span
      className={cn(
        "rounded border px-1 py-px font-mono text-[10px]",
        up ? "border-success/30 bg-success/10 text-success" : "border-critical/30 bg-critical/10 text-critical",
      )}
    >
      {up ? "▲" : "▼"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export function KpiCard({
  kpi,
  icon,
  spark,
  valueClassName,
  prefix,
  tone = "neutral",
}: {
  kpi: KpiValue;
  icon?: string;
  spark?: number[];
  valueClassName?: string;
  prefix?: string;
  tone?: Tone;
}) {
  const Icon = (icon && ICONS[icon]) || Database;
  const isNumber = typeof kpi.value === "number";
  const value = isNumber ? formatNumber(kpi.value as number) : String(kpi.value);

  return (
    <Card className="overflow-hidden border-border bg-surface shadow-panel">
      <div className={cn("h-[3px] w-full bg-gradient-to-r", TONE_BAR[tone])} />
      <CardContent className="p-4 pt-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{kpi.label}</p>
          <Icon className="h-4 w-4 shrink-0 text-slate-500" />
        </div>
        <div className="mt-1.5 flex items-baseline gap-2">
          <span className={cn("font-mono text-[22px] font-semibold leading-none tracking-tight", valueClassName)}>
            {prefix ?? ""}
            {value}
          </span>
          <DeltaChip pct={kpi.change_pct ?? null} />
        </div>
        <div className="mt-2 text-[11px] text-muted">
          <span className="truncate">{kpi.detail ?? kpi.compare_label}</span>
        </div>
        <div className="mt-auto text-accent/60">
          <Sparkline points={spark ?? []} />
        </div>
      </CardContent>
    </Card>
  );
}