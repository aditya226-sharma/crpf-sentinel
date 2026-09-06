import { api } from "@/lib/api";
import type {
  Agent,
  AgentEventItem,
  Alert,
  AlertDetail,
  AnalyticsTop,
  AssetItem,
  AuditLog,
  DashboardSummary,
  EventDetail,
  Incident,
  IncidentDetail,
  IncidentEventItem,
  IncidentNote,
  IocEntry,
  LoginResponse,
  MitreTechnique,
  NormalizedEvent,
  Notification,
  Paginated,
  Role,
  Rule,
  RuleTestResult,
  SearchResults,
  Stats,
  ThreatActivity,
  TimelinePoint,
  Unit,
  UnitStats,
  User,
  GraphCommunity,
  GraphNodeItem,
  GraphOverview,
  GraphRelationships,
} from "@/types";

// Auth
export const authService = {
  login: (username: string, password: string, rememberMe: boolean) =>
    api.post<LoginResponse>("/api/auth/login", { username, password, remember_me: rememberMe }, false),
  me: () => api.get<User>("/api/auth/me"),
  logout: () => api.post<void>("/api/auth/logout"),
  changePassword: (current_password: string, new_password: string) =>
    api.put<void>("/api/auth/password", { current_password, new_password }),
};

// Dashboard
export const dashboardService = {
  summary: (period: string) => api.get<DashboardSummary>(`/api/dashboard/summary?period=${period}`),
  timeline: (period: string) => api.get<TimelinePoint[]>(`/api/dashboard/timeline?period=${period}`),
  severity: () => api.get<{ severity: string; count: number; pct: number }[]>("/api/dashboard/severity"),
  liveEvents: (limit = 20) => api.get<NormalizedEvent[]>(`/api/dashboard/live-events?limit=${limit}`),
  activeThreats: (limit = 10) => api.get<DashboardSummary["active_threats"]>(`/api/dashboard/active-threats?limit=${limit}`),
  unitOverview: () => api.get<DashboardSummary["units"]>("/api/dashboard/unit-overview"),
};

// Logs
export interface LogFilters {
  q?: string;
  event_id?: number;
  severity?: string;
  category?: string;
  unit_id?: string;
  hostname?: string;
  username?: string;
  source_ip?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
  sort?: string;
}

export const logService = {
  list: (filters: LogFilters) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    });
    return api.get<Paginated<NormalizedEvent>>(`/api/logs?${params.toString()}`);
  },
  detail: (id: number | string) => api.get<EventDetail>(`/api/logs/${id}`),
  related: (id: number | string, limit = 10) => api.get<NormalizedEvent[]>(`/api/logs/${id}/related?limit=${limit}`),
};

// Alerts
export const alertService = {
  list: (params: Record<string, string | number | undefined>) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
    });
    return api.get<Paginated<Alert>>(`/api/alerts?${p.toString()}`);
  },
  detail: (id: string) => api.get<AlertDetail>(`/api/alerts/${id}`),
  update: (id: string, body: { status?: string; assigned_to?: string }) =>
    api.patch<Alert>(`/api/alerts/${id}`, body),
};

// Rules
export const ruleService = {
  list: (params: { category?: string; severity?: string; status?: string; q?: string } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) p.set(k, v);
    });
    return api.get<Rule[]>(`/api/rules?${p.toString()}`);
  },
  create: (body: Partial<Rule>) => api.post<Rule>("/api/rules", body),
  update: (id: string, body: Partial<Rule>) => api.put<Rule>(`/api/rules/${id}`, body),
  remove: (id: string) => api.delete<void>(`/api/rules/${id}`),
  test: (id: string, body: Record<string, unknown>) => api.post<RuleTestResult>(`/api/rules/${id}/test`, body),
  stats: (id: string) => api.get<Record<string, number | string>>(`/api/rules/${id}/stats`),
  matches: (id: string, limit = 50) => api.get<Record<string, unknown>[]>(`/api/rules/${id}/matches?limit=${limit}`),
  signatures: () => api.get<Record<string, { rule_id: string; name: string; severity: string; event_id: number[]; mitre_name: string | null; times_matched: number }[]>>("/api/signatures"),
};

// Agents
export const agentService = {
  list: (params: { status?: string; unit_id?: string; q?: string } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) p.set(k, v);
    });
    return api.get<Agent[]>(`/api/agents?${p.toString()}`);
  },
  register: (body: Record<string, unknown>) => api.post<{ agent: Agent; api_token: string }>("/api/agents", body),
  detail: (id: string) => api.get<Agent>(`/api/agents/${id}`),
  events: (id: string, limit = 50) => api.get<AgentEventItem[]>(`/api/agents/${id}/events?limit=${limit}`),
  update: (id: string, body: Record<string, unknown>) => api.patch<Agent>(`/api/agents/${id}`, body),
  revoke: (id: string) => api.delete<void>(`/api/agents/${id}`),
};

// Units
export const unitService = {
  list: () => api.get<Unit[]>("/api/units"),
  detail: (id: string) => api.get<UnitStats>(`/api/units/${id}`),
};

// Users
export const userService = {
  list: () => api.get<User[]>("/api/users"),
  create: (body: Record<string, unknown>) => api.post<User>("/api/users", body),
  update: (id: string, body: Record<string, unknown>) => api.patch<User>(`/api/users/${id}`, body),
  roles: () => api.get<Role[]>("/api/roles"),
};

// Audit
export const auditService = {
  list: (params: { action?: string; category?: string; q?: string; page?: number; page_size?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) p.set(k, String(v));
    });
    return api.get<Paginated<AuditLog>>(`/api/audit-logs?${p.toString()}`);
  },
};

// Notifications
export const notificationService = {
  list: (limit = 50) => api.get<Notification[]>(`/api/notifications?limit=${limit}`),
  unreadCount: () => api.get<{ count: number }>("/api/notifications/unread-count"),
  markRead: (id: string) => api.post<void>(`/api/notifications/${id}/read`),
  markAllRead: () => api.post<void>("/api/notifications/read-all"),
};

// Reports
export const reportService = {
  download: (reportType: string, format: "csv" | "json", unitId?: string) => {
    const params = new URLSearchParams({ format });
    if (unitId) params.set("unit_id", unitId);
    return api.raw(`/api/reports/${reportType}?${params.toString()}`);
  },
};

// Stats
export const statsService = {
  get: () => api.get<Stats>("/api/stats"),
};

// Incidents / Case Management
export const incidentService = {
  list: (params: { status?: string; severity?: string; unit_id?: string; q?: string; page?: number; page_size?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
    });
    return api.get<Paginated<Incident>>(`/api/incidents?${p.toString()}`);
  },
  detail: (id: string) => api.get<IncidentDetail>(`/api/incidents/${id}`),
  create: (body: Partial<Incident> & { alert_ids?: string[] }) => api.post<Incident>("/api/incidents", body),
  update: (id: string, body: Partial<Incident>) => api.patch<Incident>(`/api/incidents/${id}`, body),
  addAlerts: (id: string, alertIds: string[]) => api.post<{ incident_id: string; added: number }>(`/api/incidents/${id}/alerts`, { alert_ids: alertIds }),
  events: (id: string, limit = 100) => api.get<IncidentEventItem[]>(`/api/incidents/${id}/events?limit=${limit}`),
  addNote: (id: string, content: string) => api.post<IncidentNote>(`/api/incidents/${id}/notes`, { content }),
};

// IOC Library
export const iocService = {
  list: (params: { ioc_type?: string; severity?: string; status?: string; q?: string; page?: number; page_size?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
    });
    return api.get<Paginated<IocEntry>>(`/api/ioc?${p.toString()}`);
  },
  create: (body: Partial<IocEntry>) => api.post<IocEntry>("/api/ioc", body),
  update: (id: string, body: Partial<IocEntry>) => api.patch<IocEntry>(`/api/ioc/${id}`, body),
  remove: (id: string) => api.delete<void>(`/api/ioc/${id}`),
};

// MITRE ATT&CK
export const mitreService = {
  techniques: () => api.get<{ items: MitreTechnique[]; total_techniques: number }>("/api/mitre/techniques"),
};

// Analytics
export const analyticsService = {
  top: () => api.get<AnalyticsTop>("/api/analytics/top"),
  threatActivity: () => api.get<ThreatActivity>("/api/analytics/threat-activity"),
};

// Global Search
export const searchService = {
  all: (q: string) => api.get<SearchResults>(`/api/search?q=${encodeURIComponent(q)}`),
};

// Assets
export const assetService = {
  list: (params: { unit_id?: string; status?: string } = {}) => {
    const p = new URLSearchParams();
    if (params.unit_id) p.set("unit_id", params.unit_id);
    if (params.status) p.set("status", params.status);
    const qs = p.toString();
    return api.get<{ items: AssetItem[]; total: number }>(`/api/assets${qs ? `?${qs}` : ""}`);
  },
};

// Criminal Intelligence graph
export const graphService = {
  overview: () => api.get<GraphOverview>("/api/graph/overview"),
  entities: (params: { entity_type?: string; q?: string; limit?: number } = {}) => {
    const p = new URLSearchParams();
    if (params.entity_type) p.set("entity_type", params.entity_type);
    if (params.q) p.set("q", params.q);
    if (params.limit) p.set("limit", String(params.limit));
    const qs = p.toString();
    return api.get<{ items: GraphNodeItem[] }>(`/api/graph/entities${qs ? `?${qs}` : ""}`);
  },
  relationships: (entityId: string, depth = 1) =>
    api.get<GraphRelationships>(`/api/graph/relationships?entity_id=${entityId}&depth=${depth}`),
  central: (limit = 20) => api.get<{ items: GraphNodeItem[] }>(`/api/graph/central?limit=${limit}`),
  communities: (limit = 20) => api.get<{ items: GraphCommunity[] }>(`/api/graph/communities?limit=${limit}`),
  connectivity: (a: string, b: string) =>
    api.get<{ path: GraphNodeItem[]; hops: number }>(`/api/graph/connectivity?entity_a=${a}&entity_b=${b}`),
  search: (q: string, limit = 20) => api.get<{ items: GraphNodeItem[] }>(`/api/graph/search?q=${encodeURIComponent(q)}&limit=${limit}`),
};
