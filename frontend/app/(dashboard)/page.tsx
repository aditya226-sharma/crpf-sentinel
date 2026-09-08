"use client";

import { useRouter } from "next/navigation";
import { Activity, ArrowRight } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function DashboardPickerPage() {
  const router = useRouter();

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center py-12">
      <div className="mb-8 text-center">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">
          CyberRakshak · SI-16 Unified Investigation Platform
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-foreground">Select a Dashboard</h1>
        <p className="mt-1 text-sm text-muted">
          One ingestion pipeline. Specialist log-analysis workspace.
        </p>
      </div>

      <div className="grid w-full max-w-3xl gap-5 sm:grid-cols-1">
        <Card className="transition-colors hover:border-accent/50">
          <CardHeader>
            <div className="flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/10 text-accent">
                <Activity className="h-4 w-4" />
              </span>
              <div>
                <CardTitle>Log Intelligence</CardTitle>
                <CardDescription>IT system log analysis &amp; threat detection</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="min-h-16 text-xs leading-relaxed text-muted">
              Windows Event Log, Syslog/CEF, NetFlow and IPsec VPN flows through one universal
              parser. Signature detection, risk scoring, workflow, MITRE mapping and live SOC
              monitoring.
            </p>
            <Button className="mt-4 w-full" onClick={() => router.push("/dashboard")}>
              Open Log Intelligence <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}