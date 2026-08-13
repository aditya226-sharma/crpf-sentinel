"use client";

import Link from "next/link";
import { useState } from "react";
import { MapPin, Activity } from "lucide-react";
import type { UnitOverviewItem } from "@/types";
import { formatCompact } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Accurate simplified India silhouette (projected to the 300x340 canvas).
// Generated from the datameet India composite boundary, simplified with
// Douglas-Peucker and projected with the same lon/lat mapping as the unit nodes.
const INDIA_PATH = "M 107.4 37.46 L 110.76 37.7 L 118.84 32.47 L 123.01 32.33 L 126.09 35.89 L 128.61 36.26 L 129.09 38.09 L 130.38 36.54 L 132.14 37.54 L 129.25 45.42 L 124.42 47.99 L 125.26 50.19 L 123.52 52.6 L 119.1 52.9 L 120.84 56.32 L 119.28 56.49 L 119.56 58.95 L 120.99 60.79 L 123.56 60.9 L 122.9 62.82 L 124.76 66.13 L 119.8 69.61 L 117.84 65.93 L 114.9 67.63 L 118.18 73.1 L 118.17 80.05 L 120.92 78.6 L 123.72 83.01 L 127.48 83.53 L 130.66 85.67 L 130.49 87.53 L 137.44 90.93 L 131.75 96.02 L 129.26 105.45 L 138.97 110.18 L 139.89 112.5 L 144.74 115.32 L 151.78 116.69 L 152.01 118.94 L 156.99 120.7 L 157.6 119.17 L 161.66 120.54 L 164.12 118.79 L 168.13 120.61 L 168.33 123.6 L 173.19 126.54 L 176.74 125.36 L 178.66 128.48 L 182.78 127.96 L 186.18 129.96 L 189.09 128.3 L 191.4 130.73 L 196.08 129.31 L 197.11 130.59 L 198.63 126.74 L 196.93 122.85 L 198.04 114.7 L 202.48 112.66 L 204.63 115.33 L 203.56 118.29 L 204.86 121.1 L 203.41 122.62 L 206.73 126.03 L 212.95 127.11 L 217.18 125.08 L 220.27 126.42 L 231.72 125.63 L 232.3 121.14 L 231.38 119.16 L 228.27 119.14 L 228.19 116.3 L 230.59 116.76 L 233.33 115.0 L 235.14 115.97 L 237.48 114.08 L 237.03 112.32 L 243.43 107.11 L 250.57 104.35 L 250.85 102.1 L 253.7 100.64 L 259.14 102.96 L 265.91 99.75 L 268.04 101.69 L 267.05 103.27 L 268.27 102.5 L 270.85 106.37 L 268.92 108.7 L 269.71 109.48 L 271.54 107.62 L 273.36 110.26 L 277.08 111.77 L 277.38 113.74 L 273.06 117.88 L 275.18 123.14 L 271.47 120.27 L 267.4 121.22 L 258.17 127.99 L 258.48 133.53 L 253.77 140.45 L 254.45 145.15 L 249.68 156.24 L 242.6 153.86 L 243.09 163.52 L 240.87 164.45 L 241.52 172.41 L 238.99 175.7 L 237.22 173.52 L 236.39 175.33 L 233.64 157.55 L 230.87 157.4 L 230.99 160.01 L 229.21 161.83 L 229.84 163.95 L 227.98 165.54 L 226.21 162.0 L 225.66 163.85 L 224.05 158.66 L 225.89 153.59 L 227.7 153.95 L 229.06 152.16 L 230.4 153.29 L 230.56 151.25 L 232.64 150.42 L 233.22 145.5 L 235.5 145.74 L 234.88 144.17 L 231.77 142.57 L 217.91 143.01 L 212.76 141.49 L 213.17 134.83 L 211.39 131.84 L 210.52 134.59 L 208.63 134.2 L 206.33 130.22 L 204.77 130.11 L 206.02 131.81 L 202.73 131.59 L 203.41 130.72 L 200.45 127.88 L 199.87 129.36 L 201.52 130.61 L 198.55 132.77 L 197.95 136.16 L 201.65 139.29 L 203.97 139.14 L 205.66 141.78 L 200.81 142.33 L 200.45 145.04 L 198.21 145.13 L 197.11 147.87 L 203.32 151.84 L 203.61 154.87 L 201.81 158.27 L 203.88 159.82 L 203.18 162.29 L 205.55 162.7 L 204.26 164.8 L 206.44 178.81 L 204.39 177.38 L 204.3 179.02 L 203.21 178.39 L 203.69 174.96 L 202.5 174.33 L 201.78 176.99 L 200.95 176.17 L 200.89 179.06 L 199.39 177.82 L 199.14 179.58 L 198.82 173.58 L 197.2 172.83 L 198.66 174.04 L 195.36 178.2 L 189.27 179.83 L 187.73 181.86 L 187.0 183.92 L 188.27 187.14 L 187.35 187.6 L 189.08 188.16 L 186.19 190.06 L 185.69 192.52 L 186.76 191.98 L 183.11 196.01 L 171.7 201.73 L 163.93 212.77 L 148.34 225.75 L 148.33 230.63 L 139.46 233.36 L 136.64 239.3 L 134.41 237.47 L 130.88 239.69 L 129.03 245.79 L 131.58 264.07 L 129.96 272.45 L 126.56 280.52 L 127.6 294.41 L 122.58 294.93 L 119.22 302.83 L 121.69 304.93 L 113.79 307.61 L 112.12 314.19 L 107.67 317.25 L 103.07 314.42 L 99.08 308.81 L 100.11 307.85 L 99.02 308.47 L 97.47 304.07 L 93.3 286.11 L 87.58 277.13 L 84.37 268.62 L 81.73 254.29 L 72.67 235.8 L 70.39 223.11 L 71.32 223.16 L 68.18 213.71 L 69.63 214.48 L 69.5 212.67 L 68.08 212.38 L 67.96 210.42 L 68.81 211.17 L 67.54 208.85 L 68.24 207.51 L 68.9 208.63 L 67.98 206.77 L 69.33 205.51 L 68.64 203.79 L 67.1 206.81 L 66.93 202.61 L 68.01 202.78 L 66.57 201.03 L 67.81 200.37 L 66.45 200.32 L 65.81 197.22 L 68.16 187.77 L 66.48 185.33 L 67.46 184.98 L 66.25 184.42 L 66.95 183.47 L 65.68 184.49 L 66.55 183.29 L 65.32 182.27 L 68.14 178.41 L 64.8 178.54 L 66.62 175.38 L 64.55 175.35 L 65.22 173.02 L 68.01 172.4 L 63.0 171.96 L 61.6 175.52 L 62.83 178.91 L 61.16 183.28 L 50.13 188.47 L 44.44 184.75 L 34.0 171.97 L 35.14 170.22 L 36.5 172.49 L 44.59 169.57 L 46.93 165.2 L 44.98 164.33 L 40.63 167.57 L 36.23 166.57 L 31.4 163.17 L 31.81 161.82 L 29.64 159.7 L 32.93 155.93 L 27.47 158.6 L 28.99 157.45 L 27.62 157.48 L 29.05 154.95 L 32.44 154.98 L 32.91 151.49 L 43.32 152.94 L 47.9 150.39 L 49.21 152.49 L 52.68 150.58 L 51.64 150.15 L 52.48 147.66 L 48.79 140.43 L 48.75 137.32 L 45.4 137.2 L 43.96 134.91 L 44.59 128.65 L 38.92 126.69 L 39.57 122.2 L 46.29 113.74 L 48.14 113.76 L 50.56 116.87 L 59.34 114.26 L 63.54 106.01 L 68.3 103.37 L 72.15 94.0 L 77.08 91.42 L 76.75 88.45 L 83.26 82.49 L 81.68 81.89 L 82.91 78.89 L 81.47 75.94 L 82.5 74.16 L 89.05 70.73 L 86.73 68.16 L 83.14 68.0 L 83.34 64.44 L 80.49 65.18 L 74.18 61.87 L 73.84 53.73 L 72.17 48.76 L 78.44 41.2 L 75.17 40.16 L 75.48 37.06 L 72.22 37.01 L 69.84 35.05 L 70.28 33.63 L 65.07 33.72 L 64.9 29.83 L 69.29 25.09 L 75.89 24.96 L 74.32 22.86 L 77.66 23.69 L 83.33 21.0 L 85.02 22.61 L 89.34 22.35 L 89.8 24.76 L 92.15 24.52 L 94.65 27.72 L 100.56 30.57 L 101.59 33.64 L 107.32 36.49 L 107.4 37.46 Z";

const REGION_LABELS: { label: string; lat: number; lon: number }[] = [
  { label: "NORTH", lat: 33.5, lon: 76.5 },
  { label: "WEST", lat: 26.2, lon: 72.0 },
  { label: "CENTRAL", lat: 22.5, lon: 80.0 },
  { label: "EAST", lat: 24.0, lon: 86.0 },
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
              <path
                d={INDIA_PATH}
                fill="rgba(34,211,238,0.04)"
                stroke="#22D3EE"
                strokeWidth="0.8"
                strokeOpacity="0.35"
                strokeLinejoin="round"
              />
              <path
                d={INDIA_PATH}
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
                <p className="text-[10px] text-muted/70">Live unit security posture</p>
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
