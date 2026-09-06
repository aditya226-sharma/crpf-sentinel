"use client";

import { HardDriveDownload } from "lucide-react";
import type { AgentHealthItem } from "@/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function mb(bufBytes: number): string {
  return `${(bufBytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Air-gap resilience status: surfaces agents that are buffering locally
 * (queueing events because the backend was unreachable). A non-zero
 * buffer_size means the shipper has spooled events locally and is draining
 * them — zero data loss across an outage.
 */
export function AgentConnectionStatus({ agents }: { agents: AgentHealthItem[] }) {
  const buffering = agents.filter((a) => (a.buffer_size ?? 0) > 0 && a.status === "online");
  const totalBuffered = buffering.reduce((sum, a) => sum + (a.buffer_size ?? 0), 0);

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] font-medium text-foreground">
          <HardDriveDownload className="h-3.5 w-3.5 text-accent" />
          Air-Gap Resilience
        </div>
        <Badge variant={buffering.length > 0 ? "medium" : "success"} className="text-[9px]">
          {buffering.length > 0 ? `${buffering.length} buffering` : "all synced"}
        </Badge>
      </div>

      {buffering.length > 0 ? (
        <div className="mt-2 space-y-1">
          <p className="text-[10px] text-muted">
            Agents were offline and have queued events locally — draining on reconnect with no
            loss.
          </p>
          <div className="space-y-1">
            {buffering.map((a) => (
              <div key={a.id} className="flex items-center justify-between text-[10px]">
                <span className="font-mono text-foreground">{a.hostname}</span>
                <span className={cn("font-mono", (a.buffer_size ?? 0) > 0 ? "text-medium" : "text-muted")}>
                  {mb(a.buffer_size ?? 0)} buffered
                  {a.sync_status ? ` · ${a.sync_status}` : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="mt-1 text-[10px] text-muted">
          {totalBuffered === 0
            ? "All agents are connected and streaming live — no local queue."
            : "Local queues drained to zero — no data loss."}
        </p>
      )}
    </div>
  );
}
