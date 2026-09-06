"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, UserCircle2, Menu } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useClock } from "@/hooks/use-utils";
import { useLiveStream } from "@/hooks/use-live-stream";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NotificationDrawer } from "@/components/layout/notification-drawer";
import { CommandSearch, SearchButton } from "@/components/layout/command-search";

const connectionLabel = {
  live: "LIVE",
  connecting: "CONNECTING",
  reconnecting: "RECONNECTING",
  offline: "OFFLINE",
} as const;

const connectionVariant = {
  live: "success",
  connecting: "accent",
  reconnecting: "medium",
  offline: "default",
} as const;

const PAGE_TITLES: Record<string, { section: string; page: string }> = {
  "/criminal": { section: "CRIMINAL INTELLIGENCE", page: "Network Map" },
  "/dashboard": { section: "LOG INTELLIGENCE", page: "Command Center" },
  "/live-events": { section: "LOG INTELLIGENCE", page: "Live Events" },
  "/logs": { section: "MONITORING", page: "Log Explorer" },
  "/alerts": { section: "MONITORING", page: "Security Alerts" },
  "/incidents": { section: "MONITORING", page: "Incidents" },
  "/search": { section: "MONITORING", page: "Search" },
  "/units": { section: "INFRASTRUCTURE", page: "CRPF Units" },
  "/agents": { section: "INFRASTRUCTURE", page: "Windows Agents" },
  "/assets": { section: "INFRASTRUCTURE", page: "Assets" },
  "/rules": { section: "DETECTION", page: "Detection Rules" },
  "/threat-intel": { section: "DETECTION", page: "Threat Intelligence" },
  "/ioc-library": { section: "DETECTION", page: "IOC Library" },
  "/mitre": { section: "DETECTION", page: "MITRE ATT&CK" },
  "/threat-analytics": { section: "ANALYTICS", page: "Threat Analytics" },
  "/risk-overview": { section: "ANALYTICS", page: "Risk Overview" },
  "/correlations": { section: "ANALYTICS", page: "Correlations" },
  "/reports": { section: "ANALYTICS", page: "Reports" },
  "/users": { section: "ADMINISTRATION", page: "Users & Roles" },
  "/audit-logs": { section: "ADMINISTRATION", page: "Audit Logs" },
  "/settings": { section: "ADMINISTRATION", page: "Settings" },
};

export function Topbar({ collapsed: _collapsed }: { collapsed: boolean }) {
  const { user, logout } = useAuth();
  const { connection } = useLiveStream();
  const clock = useClock();
  const router = useRouter();
  const pathname = usePathname();
  const [searchOpen, setSearchOpen] = useState(false);

  const crumbs = Object.entries(PAGE_TITLES).find(([base]) => pathname === base || pathname.startsWith(`${base}/`));
  const section = crumbs?.[1].section ?? "COMMAND CENTER";
  const page = crumbs?.[1].page ?? "Console";

  return (
    <header className="fixed inset-x-0 top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur lg:px-6">
      <div className="hidden items-center gap-1.5 text-xs sm:flex">
        <span className="text-muted">{section}</span>
        <span className="text-slate-600">/</span>
        <span className="font-medium text-foreground">{page}</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <SearchButton onOpen={() => setSearchOpen(true)} />
        <Badge variant={connectionVariant[connection]} className="text-[9px]">
          <span className="relative flex h-1.5 w-1.5">
            <span className={connection === "live" ? "absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" : "hidden"} />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
          </span>
          {connectionLabel[connection]}
        </Badge>

        <span className="hidden font-mono text-[11px] text-slate-500 xl:inline">{clock}</span>

        <NotificationDrawer />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full" aria-label="Account">
              <UserCircle2 className="h-[18px] w-[18px]" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="text-xs font-medium text-foreground">{user?.full_name ?? user?.username}</div>
              <div className="mt-0.5 text-[11px] font-normal text-muted">
                {user?.role?.name ?? "User"} · {user?.id?.slice(0, 8) ?? ""}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")}>Account Settings</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onClick={() => void logout()}>
              <LogOut className="h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <CommandSearch open={searchOpen} onOpenChange={setSearchOpen} />
    </header>
  );
}
