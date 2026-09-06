"use client";

import { Shield, TrendingDown, TrendingUp } from "lucide-react";
import type { KpiValue } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function gradeFor(score: number): { grade: string; label: string; color: string; bar: string } {
  if (score >= 75) return { grade: "D", label: "High Risk", color: "#EF4444", bar: "#EF4444" };
  if (score >= 50) return { grade: "C", label: "Elevated", color: "#F59E0B", bar: "#F59E0B" };
  if (score >= 25) return { grade: "B", label: "Guarded", color: "#38BDF8", bar: "#38BDF8" };
  return { grade: "A", label: "Resilient", color: "#22C55E", bar: "#22C55E" };
}

export function ExecutiveRiskGauge({ risk }: { risk: KpiValue | undefined }) {
  const score = typeof risk?.value === "number" ? risk.value : Number(risk?.value ?? 0);
  const { grade, label, color, bar } = gradeFor(score);
  const pct = Math.max(0, Math.min(100, score));
  const improving = typeof risk?.change_pct === "number" && risk.change_pct < 0;

  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-accent" />
          Executive Risk Posture
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <div
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-4 text-2xl font-bold"
            style={{ borderColor: color, color }}
          >
            {grade}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold" style={{ color }}>{label}</p>
            <p className="font-mono text-xs text-muted">Risk {score}/100</p>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface2">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: bar }} />
            </div>
            <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted">
              {typeof risk?.change_pct === "number" && risk.change_pct !== 0 ? (
                improving ? (
                  <><TrendingDown className="h-3 w-3 text-success" /> improving vs previous period</>
                ) : (
                  <><TrendingUp className="h-3 w-3 text-critical" /> worsening vs previous period</>
                )
              ) : (
                <span className="italic">overall posture across monitored units</span>
              )}
            </div>
          </div>
        </div>
        <p className={cn("mt-3 text-[10px] text-muted")}>
          {risk?.detail ?? "Computed from open alert risk scores across all units."}
        </p>
      </CardContent>
    </Card>
  );
}
