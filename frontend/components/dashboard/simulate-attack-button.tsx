"use client";

import { useState } from "react";
import { Bug, CheckCircle2, Loader2, RotateCcw, Zap } from "lucide-react";
import { demoService } from "@/services";
import type { DemoSimulateAlert, DemoSimulateResult } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { useAuth } from "@/hooks/use-auth";

const PHASE_LABELS: Record<string, string> = {
  recon: "Reconnaissance",
  initial_access: "Initial Access",
  privilege_escalation: "Privilege Escalation",
  lateral_movement: "Lateral Movement",
  persistence: "Persistence",
  defence_evasion: "Defence Evasion",
  exfiltration: "Exfiltration",
  persistence_account: "Rogue Account",
};

export function SimulateAttackButton() {
  const { user } = useAuth();
  const isAdmin = user?.role?.name === "super_admin";
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DemoSimulateResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isAdmin) return null;

  async function run() {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await demoService.simulate();
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-1.5" onClick={() => void run()} disabled={running}>
          {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bug className="h-3.5 w-3.5" />}
          {running ? "Simulating attack…" : "Simulate Attack"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-muted"
          onClick={() => setResult(null)}
          disabled={!result || running}
        >
          <RotateCcw className="h-3 w-3" />
          Clear
        </Button>
      </div>

      {error && <p className="text-[11px] text-critical">{error}</p>}

      {result && (
        <div className="rounded-md border border-border bg-surface p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-foreground">
              <Zap className="h-3.5 w-3.5 text-accent" />
              Multi-stage attack replay · live pipeline
            </p>
            <Badge variant="accent" className="text-[9px]">
              {result.events_ingested} events · {result.alerts_fired.length} alerts
            </Badge>
          </div>

          <div className="mt-2 flex flex-wrap gap-1">
            {result.phases.map((p) => (
              <span
                key={p}
                className="flex items-center gap-1 rounded-full border border-border bg-surface2 px-2 py-0.5 text-[9px] text-muted"
              >
                <CheckCircle2 className="h-2.5 w-2.5 text-success" />
                {PHASE_LABELS[p] ?? p}
              </span>
            ))}
          </div>

          {result.alerts_fired.length > 0 && (
            <div className="mt-2 space-y-1">
              {result.alerts_fired.map((a: DemoSimulateAlert) => (
                <div key={a.id} className="flex items-center justify-between gap-2 rounded bg-surface2/60 px-2 py-1 text-[10px]">
                  <span className="truncate text-foreground">{a.title}</span>
                  <span className="flex shrink-0 items-center gap-1.5">
                    <SeverityBadge severity={a.severity} className="text-[8px]" />
                    <span className="font-mono text-muted">{a.risk_score}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
