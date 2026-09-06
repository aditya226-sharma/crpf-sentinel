"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  FileSearch,
  Radio,
  Bell,
  Siren,
  Building2,
  Network,
  MonitorSmartphone,
  ShieldAlert,
  Crosshair,
  Target,
  BarChart3,
  FileBarChart,
  Users,
  History,
  Settings,
  Radar,
  ChevronsLeft,
  ChevronsRight,
  Gauge,
  Fingerprint,
  LayoutGrid,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Brand } from "@/components/layout/brand";
import { Badge } from "@/components/ui/badge";
import { useAlertCount } from "@/hooks/use-queries";
import { useAuth } from "@/hooks/use-auth";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  permissions?: string[];
}

const navGroups: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspaces",
    items: [
      { href: "/", label: "Dashboard Select", icon: LayoutGrid },
    ],
  },
  {
    title: "Criminal Intelligence",
    items: [
      { href: "/criminal", label: "Network Map", icon: Fingerprint, permissions: ["graph.view"] },
    ],
  },
  {
    title: "Command Center",
    items: [
      { href: "/dashboard", label: "Log Intelligence Dashboard", icon: LayoutDashboard, permissions: ["dashboard.view"] },
      { href: "/live-events", label: "Live Events", icon: Radio, permissions: ["logs.view"] },
    ],
  },
  {
    title: "Monitoring",
    items: [
      { href: "/logs", label: "Logs", icon: FileSearch, permissions: ["logs.view"] },
      { href: "/alerts", label: "Alerts", icon: Bell, permissions: ["alerts.view"] },
      { href: "/incidents", label: "Incidents", icon: Siren, permissions: ["alerts.view"] },
      { href: "/search", label: "Search", icon: Search, permissions: ["logs.view"] },
    ],
  },
  {
    title: "Infrastructure",
    items: [
      { href: "/units", label: "CRPF Units", icon: Building2, permissions: ["units.view"] },
      { href: "/agents", label: "Windows Agents", icon: Network, permissions: ["agents.view"] },
      { href: "/assets", label: "Assets", icon: MonitorSmartphone, permissions: ["logs.view"] },
    ],
  },
  {
    title: "Detection",
    items: [
      { href: "/rules", label: "Detection Rules", icon: ShieldAlert, permissions: ["rules.view"] },
      { href: "/threat-intel", label: "Threat Intel", icon: Radar, permissions: ["threat_intel.view"] },
      { href: "/ioc-library", label: "IOC Library", icon: Crosshair, permissions: ["threat_intel.view"] },
      { href: "/mitre", label: "MITRE ATT&CK", icon: Target, permissions: ["threat_intel.view"] },
    ],
  },
  {
    title: "Analytics",
    items: [
      { href: "/threat-analytics", label: "Threat Analytics", icon: BarChart3, permissions: ["dashboard.view"] },
      { href: "/risk-overview", label: "Risk Overview", icon: Gauge, permissions: ["dashboard.view"] },
      { href: "/correlations", label: "Correlations", icon: BarChart3, permissions: ["correlations.view"] },
      { href: "/reports", label: "Reports", icon: FileBarChart, permissions: ["reports.view"] },
    ],
  },
  {
    title: "Administration",
    items: [
      { href: "/users", label: "Users & Roles", icon: Users, permissions: ["users.manage"] },
      { href: "/audit-logs", label: "Audit Logs", icon: History, permissions: ["audit.view"] },
      { href: "/settings", label: "Settings", icon: Settings, permissions: ["dashboard.view"] },
    ],
  },
];

const SECTION_LABELS: Record<string, string> = {
  "/criminal": "CRIMINAL INTELLIGENCE",
  "/dashboard": "LOG INTELLIGENCE",
  "/live-events": "COMMAND CENTER",
  "/logs": "MONITORING",
  "/alerts": "MONITORING",
  "/incidents": "MONITORING",
  "/search": "MONITORING",
  "/units": "INFRASTRUCTURE",
  "/agents": "INFRASTRUCTURE",
  "/assets": "INFRASTRUCTURE",
  "/rules": "DETECTION",
  "/threat-intel": "DETECTION",
  "/ioc-library": "DETECTION",
  "/mitre": "DETECTION",
  "/threat-analytics": "ANALYTICS",
  "/risk-overview": "ANALYTICS",
  "/correlations": "ANALYTICS",
  "/reports": "ANALYTICS",
  "/users": "ADMINISTRATION",
  "/audit-logs": "ADMINISTRATION",
  "/settings": "ADMINISTRATION",
};

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const pathname = usePathname();
  const { can, user } = useAuth();
  const { data: alertCount } = useAlertCount();

  const visibleGroups = navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.permissions || item.permissions.some((p) => can(p)),
      ),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <TooltipProvider delayDuration={150}>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-surface3 transition-[width] duration-200",
          collapsed ? "w-[72px]" : "w-[250px]",
        )}
      >
        <div className={cn("flex h-16 items-center border-b border-border", collapsed ? "justify-center px-0" : "px-5")}>
          <Brand collapsed={collapsed} />
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {visibleGroups.map((group, i) => (
            <div key={i} className="mb-4">
              {!collapsed && (
                <div className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted/70">
                  {group.title}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  const showAlertCount = item.href === "/alerts" && (alertCount ?? 0) > 0;

                  const link = (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "group flex items-center gap-3 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors",
                        collapsed && "justify-center px-0",
                        active
                          ? "bg-accent/10 text-accent"
                          : "text-slate-400 hover:bg-surface hover:text-foreground",
                      )}
                    >
                      <Icon className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-slate-500 group-hover:text-slate-300")} />
                      {!collapsed && (
                        <>
                          <span className="flex-1">{item.label}</span>
                          {showAlertCount && (
                            <Badge variant="critical" className="px-1.5 py-0 text-[10px]">
                              {alertCount}
                            </Badge>
                          )}
                        </>
                      )}
                    </Link>
                  );

                  return collapsed ? (
                    <Tooltip key={item.href}>
                      <TooltipTrigger asChild>{link}</TooltipTrigger>
                      <TooltipContent side="right" className="text-[11px]">
                        {item.label}
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    link
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-border px-4 py-3">
          {collapsed ? (
            <div className="flex flex-col items-center gap-3">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
              <button
                onClick={onToggle}
                className="rounded p-1.5 text-slate-500 hover:bg-surface hover:text-foreground"
                aria-label="Expand sidebar"
              >
                <ChevronsRight className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <>
              <div className="mb-3 flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-2">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
                </span>
                <div className="flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">System Status</p>
                  <p className="font-mono text-[10px] text-success">OPERATIONAL</p>
                </div>
              </div>

              <div className="flex items-center gap-2.5 rounded-md px-1 py-1.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 font-mono text-[11px] font-bold text-accent">
                  {(user?.full_name ?? user?.username ?? "U")
                    .split(" ")
                    .map((p) => p[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] font-medium text-foreground">
                    {user?.full_name ?? user?.username ?? "Analyst"}
                  </p>
                  <p className="truncate text-[10px] text-muted">{user?.role?.name ?? "User"}</p>
                </div>
                <button
                  onClick={onToggle}
                  className="rounded p-1.5 text-slate-500 hover:bg-surface hover:text-foreground"
                  aria-label="Collapse sidebar"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </button>
              </div>
            </>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
}

export { SECTION_LABELS };
