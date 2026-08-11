"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, HardDrive, Cpu, ShieldAlert, Activity, FileWarning, ArrowRight } from "lucide-react";
import { demoService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { PageError, PageLoading } from "@/components/shared/page-states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Mono } from "@/components/shared/mono";
import { Button } from "@/components/ui/button";
import { DetectionPipeline, PIPELINE_STAGES } from "@/components/demo/detection-pipeline";
import { ScenarioCard, type ScenarioMeta } from "@/components/demo/scenario-card";
import { formatCompact } from "@/lib/utils";
import type { ScenarioResult } from "@/types";

const SCENARIO_META: Record<string, Omit<ScenarioMeta, "id" | "name" | "explanation">> = {
  brute_force: {
    short: "BRUTE FORCE",
    eventIds: [4625, 4624],
    eventLabel: "4625 ×10 → 4624",
    mitre: "T1110",
    severity: "high",
    detail: "Credential Access",
  },
  audit_clear: {
    short: "AUDIT LOG CLEARED",
    eventIds: [1102],
    eventLabel: "1102",
    mitre: "T1070.001",
    severity: "critical",
    detail: "Defense Evasion",
  },
  new_service: {
    short: "NEW SERVICE",
    eventIds: [7045],
    eventLabel: "7045",
    mitre: "T1543.003",
    severity: "medium",
    detail: "Persistence",
  },
  powershell: {
    short: "SUSPICIOUS POWERSHELL",
    eventIds: [4688],
    eventLabel: "4688",
    mitre: "T1059.001",
    severity: "high",
    detail: "Execution",
  },
  user_created: {
    short: "NEW USER ACCOUNT",
    eventIds: [4720],
    eventLabel: "4720",
    mitre: "T1136.001",
    severity: "medium",
    detail: "Persistence",
  },
};

export default function DemoPage() {
  const queryClient = useQueryClient();
  const [runningId, setRunningId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [lastName, setLastName] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const statusQuery = useQuery({ queryKey: ["demo", "status"], queryFn: () => demoService.status() });
  const scenariosQuery = useQuery({ queryKey: ["demo", "scenarios"], queryFn: () => demoService.scenarios() });

  const scenarios: ScenarioMeta[] = useMemo(() => {
    if (!scenariosQuery.data) return [];
    return scenariosQuery.data.map((s) => {
      const meta = SCENARIO_META[s.id];
      if (!meta) return null;
      return { id: s.id, name: meta.short, explanation: s.explanation, ...meta };
    }).filter((s): s is ScenarioMeta => s !== null);
  }, [scenariosQuery.data]);

  function reset() {
    if (timerRef.current) clearInterval(timerRef.current);
    setRunningId(null);
    setActiveStage(0);
    setDone(false);
    setError(null);
    setResult(null);
    setLastName(null);
  }

  async function runScenario(sc: ScenarioMeta) {
    reset();
    setRunningId(sc.id);
    setLastName(sc.short);
    setActiveStage(0);
    timerRef.current = setInterval(() => {
      setActiveStage((s) => Math.min(s + 1, PIPELINE_STAGES.length - 1));
    }, 400);

    try {
      const res = await demoService.run(sc.id);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scenario failed to run.");
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
      setActiveStage(PIPELINE_STAGES.length);
      setDone(true);
      setRunningId(null);
      void queryClient.invalidateQueries();
    }
  }

  const loading = statusQuery.isLoading || scenariosQuery.isLoading;
  const hasError = statusQuery.isError || scenariosQuery.isError;

  return (
    <div>
      <PageHeader
        title="Demo Center"
        description="Safe, synthetic attack scenarios that flow through the real detection pipeline."
      />

      <div className="mb-4 flex items-center gap-3 rounded-md border border-accent/30 bg-accent/5 px-4 py-3">
        <FileWarning className="h-4 w-4 shrink-0 text-accent" />
        <div>
          <p className="font-mono text-[12px] font-semibold uppercase tracking-[0.15em] text-accent">Demo Mode</p>
          <p className="text-[11px] text-muted">
            Synthetic data only — no real CRPF systems are touched. Events are generated locally and pass through the
            same parse → normalize → detect → alert pipeline as production agents.
          </p>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "Monitored Units", value: statusQuery.data?.units, icon: HardDrive },
          { label: "Agents", value: statusQuery.data?.agents, icon: Cpu },
          { label: "Events", value: statusQuery.data?.events, icon: Activity },
          { label: "Alerts", value: statusQuery.data?.alerts, icon: ShieldAlert },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-surface2">
                <s.icon className="h-4 w-4 text-accent" />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{s.label}</p>
                <p className="font-mono text-lg font-semibold text-foreground">
                  {formatCompact(s.value ?? 0)}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {loading && <PageLoading rows={6} />}
      {hasError && (
        <PageError
          message={(statusQuery.error as Error)?.message ?? (scenariosQuery.error as Error)?.message}
          onRetry={() => {
            void statusQuery.refetch();
            void scenariosQuery.refetch();
          }}
        />
      )}

      {!loading && !hasError && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-accent" />
              <h2 className="text-sm font-semibold text-foreground">Attack Scenarios</h2>
              <Badge variant="accent" className="text-[9px]">{scenarios.length} available</Badge>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {scenarios.map((s) => (
                <ScenarioCard
                  key={s.id}
                  scenario={s}
                  running={runningId === s.id}
                  disabled={runningId !== null}
                  onSimulate={() => void runScenario(s)}
                />
              ))}
            </div>

            {result && (
              <Card className="mt-4 border-accent/25">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <ShieldAlert className="h-4 w-4 text-accent" />
                    Scenario Result — <Mono>{result.scenario}</Mono>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded border border-border bg-surface3 px-3 py-2.5">
                      <p className="text-[9px] uppercase tracking-wider text-muted">Events Ingested</p>
                      <p className="mt-0.5 font-mono text-lg font-semibold text-foreground">{result.events_ingested}</p>
                    </div>
                    <div className="rounded border border-border bg-surface3 px-3 py-2.5">
                      <p className="text-[9px] uppercase tracking-wider text-muted">Alerts Triggered</p>
                      <p className={result.alerts_triggered > 0 ? "mt-0.5 font-mono text-lg font-semibold text-high" : "mt-0.5 font-mono text-lg font-semibold text-foreground"}>
                        {result.alerts_triggered}
                      </p>
                    </div>
                  </div>

                  {result.alert_ids.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-1.5 text-[9px] uppercase tracking-wider text-muted">Raised Alerts</p>
                      <div className="flex flex-wrap gap-2">
                        {result.alert_ids.map((id) => (
                          <Link key={id} href={`/alerts/detail?id=${id}`}>
                            <Badge variant="high" className="px-2 py-1 font-mono text-[10px] transition-colors hover:bg-high/20">
                              {id}
                              <ArrowRight className="h-3 w-3" />
                            </Badge>
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className="mt-3 text-[11px] leading-relaxed text-muted">
                    {lastName}: {result.explanation}
                  </p>
                  <p className="mt-2 flex items-center gap-1.5 font-mono text-[10px] text-muted">
                    <FlaskConical className="h-3 w-3" />
                    {result.demo_notice}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            <DetectionPipeline
              running={runningId !== null}
              activeStage={activeStage}
              done={done}
              error={error}
              onReset={reset}
            />
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">How it works</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-[11px] leading-relaxed text-muted">
                <p>
                  Simulating a scenario injects synthetic Windows events through the standard ingest endpoint. The
                  correlation engine matches the sequence, maps it to MITRE ATT&amp;CK, and raises an alert with a risk
                  score.
                </p>
                <div className="rounded border border-border bg-surface3 p-2.5 font-mono text-[10px] leading-relaxed text-slate-400">
                  17 Failed Logins
                  <ArrowRight className="inline h-3 w-3 text-accent" /> Detection Triggered
                  <br />
                  T1110 Brute Force
                  <ArrowRight className="inline h-3 w-3 text-accent" /> HIGH ALERT
                  <br />
                  Risk Score 82
                  <ArrowRight className="inline h-3 w-3 text-accent" /> Incident Created
                </div>
                <p>
                  Follow the raised alerts into the incident workflow to drive a case to resolution.
                </p>
                <Button variant="outline" size="sm" asChild className="w-full">
                  <Link href="/alerts">Open Security Alerts</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
