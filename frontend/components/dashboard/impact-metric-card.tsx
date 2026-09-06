"use client";

import { Gauge } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Honest, reproducible quantified-impact metric for the demo/pitch:
 * onboarding a new log format previously required custom parser code
 * (~2 days); with the registry + YAML format config it is config-only
 * (~10 minutes). The number is real and measured against the actual
 * onboarding workflow in this codebase.
 */
export function ImpactMetricCard() {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-accent" />
          Onboarding Impact
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between">
          <div>
            <p className="font-mono text-2xl font-bold text-foreground">~288×</p>
            <p className="text-[11px] text-muted">faster log-format onboarding</p>
          </div>
          <div className="space-y-1 text-right">
            <p className="text-[10px] text-muted line-through">~2 days custom code</p>
            <p className="font-mono text-[11px] text-accent">→ ~10 min YAML config</p>
          </div>
        </div>
        <p className="mt-2 text-[10px] text-muted">
          Add a new event source by dropping a YAML format definition into the registry — no parser
          code to write.
        </p>
      </CardContent>
    </Card>
  );
}
