"use client";

import { Bell, CheckCheck, Loader2, ShieldAlert } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { notificationService } from "@/services";
import { timeAgo } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const severityVariant: Record<string, "critical" | "high" | "medium" | "info" | "success"> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "info",
  informational: "info",
  system: "success",
};

export function NotificationDrawer() {
  const queryClient = useQueryClient();
  const { data: notifications, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationService.list(30),
    refetchInterval: 30_000,
  });
  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => notificationService.unreadCount(),
    refetchInterval: 30_000,
  });

  async function markAllRead() {
    await notificationService.markAllRead();
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="h-[18px] w-[18px]" />
          {(unread?.count ?? 0) > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-critical px-1 font-mono text-[9px] font-bold text-white">
              {unread?.count}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-xs font-medium text-foreground">
            <ShieldAlert className="h-3.5 w-3.5 text-accent" />
            Notifications
          </span>
          {notifications?.some((n) => !n.is_read) && (
            <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => void markAllRead()}>
              <CheckCheck className="h-3 w-3" />
              Mark all read
            </Button>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="max-h-[420px] overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-4 w-4 animate-spin text-muted" />
            </div>
          )}
          {!isLoading && (!notifications || notifications.length === 0) && (
            <div className="px-4 py-10 text-center text-xs text-muted">No notifications</div>
          )}
          {notifications?.map((n) => (
            <div
              key={n.id}
              className={n.is_read ? "border-b border-border/50 px-4 py-2.5" : "border-b border-border/50 bg-accent/5 px-4 py-2.5"}
            >
              <div className="flex items-start justify-between gap-2">
                <Badge variant={severityVariant[n.severity] ?? "info"} className="shrink-0 text-[9px]">
                  {n.severity}
                </Badge>
                <span className="text-[10px] text-muted">{timeAgo(n.created_at)}</span>
              </div>
              <p className="mt-1.5 text-[12px] leading-snug text-foreground">{n.title}</p>
              {n.alert_id && (
                <Link href={`/alerts/detail?id=${n.alert_id}`} className="mt-1 block font-mono text-[10px] text-accent hover:underline">
                  Open alert →
                </Link>
              )}
            </div>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
