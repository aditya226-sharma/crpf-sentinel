"use client";

import { useCallback, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { demoService, statsService } from "@/services";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";

type ResetStatus = "idle" | "running" | "done" | "error";

/**
 * One-click demo reset button (Tier 1.3 VAJRA).
 * Calls POST /api/demo/reset which may return immediately (background mode)
 * or synchronously.  Polls /api/stats to detect completion when async.
 */
export function ResetDemoButton({ onResetComplete }: { onResetComplete?: () => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role?.name === "super_admin";
  const [status, setStatus] = useState<ResetStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const pollForDone = useCallback(async () => {
    // Background mode: poll stats endpoint until event count is back near the
    // curated baseline (~2.8k; possibly +2.8k if an instance re-seed overlaps).
    let attempts = 0;
    const maxAttempts = 30; // 30 × 4s = 2 min max
    while (attempts < maxAttempts) {
      await new Promise((res) => setTimeout(res, 4000));
      try {
        const data = await statsService.get();
        const events = data.total_events ?? 0;
        if (events > 0 && events < 8000) {
          setStatus("done");
          setMessage(`Dashboard restored — ${events.toLocaleString()} events, ${data.total_alerts} alerts`);
          onResetComplete?.();
          return;
        }
      } catch {
        // network blip, keep trying
      }
      attempts++;
    }
    // If we exhausted polls, the reset may still be running.
    setStatus("done");
    setMessage("Reset is still processing in the background.  Refresh to check.");
    onResetComplete?.();
  }, [onResetComplete]);

  const runReset = async () => {
    setStatus("running");
    setMessage(null);
    try {
      const result = await demoService.reset();
      if (result.status === "started") {
        setMessage("Purging simulated data and re-seeding backdrop — takes a few minutes on first run");
        pollForDone();
      } else if (result.status === "busy") {
        setStatus("idle");
        setMessage("A reset is already in progress — wait and refresh.");
      } else {
        // Synchronous ok (local dev / fast DB)
        setStatus("done");
        setMessage(`Removed ${result.removed_events ?? 0} events, ${result.removed_alerts ?? 0} alerts — dashboard restored`);
        onResetComplete?.();
      }
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Reset failed");
    }
  };

  if (!isAdmin) return null;

  const running = status === "running";

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={() => void runReset()}
        disabled={running}
      >
        {running ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : status === "done" ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
        ) : status === "error" ? (
          <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
        ) : (
          <RefreshCw className="h-3.5 w-3.5" />
        )}
        {running ? "Resetting…" : "Reset Demo"}
      </Button>

      {message && (
        <Badge
          variant={status === "done" ? "success" : status === "error" ? "critical" : status === "running" ? "medium" : "outline"}
          className="max-w-[420px] truncate text-[10px]"
        >
          {message}
        </Badge>
      )}
    </div>
  );
}
