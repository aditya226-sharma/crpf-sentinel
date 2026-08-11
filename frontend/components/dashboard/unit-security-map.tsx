"use client";

import Link from "next/link";
import { useState } from "react";
import { MapPin, Activity } from "lucide-react";
import type { UnitOverviewItem } from "@/types";
import { formatCompact } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Coarse India silhouette (lat,lon) → projected to a 300x340 canvas.
// Lon 68-97 → x 26-274 ; Lat 37-8 → y 22-318
const INDIA_OUTLINE: [number, number][] = [
  [36.8, 74.6], [35.2, 73.2], [34.5, 76.0], [32.5, 75.0], [31.0, 74.8],
  [29.0, 70.5], [28.0, 70.7], [24.2, 68.5], [22.5, 69.5], [21.0, 72.0],
  [20.7, 70.2], [19.0, 72.8], [17.5, 73.5], [15.0, 73.8], [12.0, 74.9],
  [10.0, 76.0], [8.0, 77.5], [10.8, 79.8], [13.0, 80.2], [16.0, 82.3],
  [19.5, 83.0], [21.0, 86.8], [22.5, 88.3], [25.0, 89.0], [26.5, 90.0],
  [27.5, 94.0], [28.2, 96.8], [27.5, 91.5], [28.5, 88.5], [30.0, 88.0],
  [31.0, 78.5], [32.5, 79.0], [34.0, 77.5],
];

const REGION_LABELS: { label: string; lat: number; lon: number }[] = [
  { label: "NORTH", lat: 33.5, lon: 76.5 },
  { label: "WEST", lat: 24.5, lon: 70.5 },
  { label: "CENTRAL", lat: 22.5, lon: 80.0 },
  { label: "EAST", lat: 24.5, lon: 90.0 },
  { label: "SOUTH", lat: 12.5, lon: 78.5 },
];

function project(lat: number, lon: number): [number, number] {
  const x = 26 + ((lon - 68) / 29) * 248;
  const y = 22 + ((37 - lat) / 29) * 296;
  return [x, y];
}

function nodeStyle(u: UnitOverviewItem): { color: string; label: string } {
  const risk = u.risk ?? 0;
  if (u.status === "offline") return { color: "#64748B", label: "OFFLINE" };
  if (risk >= 60 || u.status === "critical") return { color: "#EF4444", label: "CRITICAL ALERT" };
  if (risk >= 35 || u.status === "warning") return { color: "#F59E0B", label: "WARNING" };
  return { color: "#22C55E", label: "NORMAL" };
}

export function UnitSecurityMap({ units }: { units: UnitOverviewItem[] }) {
  const [hovered, setHovered] = useState<UnitOverviewItem | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-accent" />
          CRPF Unit Security Map
        </CardTitle>
        <div className="flex items-center gap-3 text-[9px] text-muted">
          {[
            ["#22C55E", "Normal"],
            ["#F59E0B", "Warning"],
            ["#EF4444", "Critical"],
            ["#64748B", "Offline"],
          ].map(([c, l]) => (
            <span key={l} className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />
              {l}
            </span>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_220px]">
          <div className="relative overflow-hidden rounded-md border border-border bg-surface3">
            <svg viewBox="0 0 300 340" className="h-auto w-full">
              <defs>
                <pattern id="mapgrid" width="30" height="30" patternUnits="userSpaceOnUse">
                  <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#1E293B" strokeWidth="0.4" />
                </pattern>
              </defs>
              <rect width="300" height="340" fill="#090F1A" />
              <rect width="300" height="340" fill="url(#mapgrid)" />
              <polygon
                points={INDIA_OUTLINE.map(([lat, lon]) => project(lat, lon).join(",")).join(" ")}
                fill="rgba(34,211,238,0.04)"
                stroke="#22D3EE"
                strokeWidth="0.8"
                strokeOpacity="0.35"
                strokeLinejoin="round"
              />
              <polygon
                points={INDIA_OUTLINE.map(([lat, lon]) => project(lat, lon).join(",")).join(" ")}
                fill="none"
                stroke="#22D3EE"
                strokeWidth="2"
                strokeOpacity="0.06"
                strokeLinejoin="round"
              />
              {REGION_LABELS.map((r) => {
                const [x, y] = project(r.lat, r.lon);
                return (
                  <text key={r.label} x={x} y={y} textAnchor="middle" fontSize="6" fill="#64748B" letterSpacing="1">
                    {r.label}
                  </text>
                );
              })}
              {units.map((u) => {
                if (u.latitude == null || u.longitude == null) return null;
                const [x, y] = project(u.latitude, u.longitude);
                const { color } = nodeStyle(u);
                const critical = color === "#EF4444";
                return (
                  <Link key={u.id} href={`/units/detail?id=${u.id}`}>
                    <g
                      onMouseEnter={() => setHovered(u)}
                      onMouseLeave={() => setHovered(null)}
                      className="cursor-pointer"
                    >
                      {critical && (
                        <circle cx={x} cy={y} r="9" fill="none" stroke={color} strokeWidth="0.6" opacity="0.4">
                          <animate attributeName="r" values="5;11" dur="2s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.5;0" dur="2s" repeatCount="indefinite" />
                        </circle>
                      )}
                      <circle cx={x} cy={y} r="7" fill={color} opacity="0.14" />
                      <circle cx={x} cy={y} r="3" fill={color}>
                        {critical && (
                          <animate attributeName="opacity" values="1;0.4;1" dur="1.6s" repeatCount="indefinite" />
                        )}
                      </circle>
                    </g>
                  </Link>
                );
              })}
            </svg>
          </div>

          <div className="flex flex-col">
            {hovered ? (
              <div className="flex-1 rounded-md border border-border bg-surface p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-mono text-[13px] font-semibold text-accent">{hovered.unit_code}</p>
                  <Badge
                    variant={nodeStyle(hovered).color === "#22C55E" ? "success" : nodeStyle(hovered).color === "#F59E0B" ? "medium" : "critical"}
                    className="text-[9px]"
                  >
                    {nodeStyle(hovered).label}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-foreground">{hovered.name}</p>
                <p className="text-[11px] text-muted">{hovered.city ?? "—"}</p>
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted">Agents</span>
                    <span className="font-mono text-foreground">{hovered.agents}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted">Events</span>
                    <span className="font-mono text-foreground">{formatCompact(hovered.events)}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted">Alerts</span>
                    <span className="font-mono text-foreground">{hovered.alerts}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted">Risk</span>
                    <span className={cn("font-mono", hovered.risk >= 60 ? "text-critical" : hovered.risk >= 35 ? "text-medium" : "text-success")}>
                      {hovered.risk}
                    </span>
                  </div>
                </div>
                <Link href={`/units/detail?id=${hovered.id}`} className="mt-4 block rounded-md border border-accent/30 bg-accent/10 px-2.5 py-1.5 text-center text-[11px] font-medium text-accent hover:bg-accent/20">
                  Open Unit Details →
                </Link>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border p-4 text-center">
                <Activity className="h-5 w-5 text-slate-600" />
                <p className="text-[11px] text-muted">Hover a unit node to inspect posture.</p>
                <p className="text-[10px] text-muted/70">Synthetic deployment map · no operational data</p>
              </div>
            )}
            <div className="mt-3 rounded-md border border-border bg-surface px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wider text-muted">Monitored units</span>
                <span className="font-mono text-xs text-foreground">{units.length}</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
