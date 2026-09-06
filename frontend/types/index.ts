export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  role_id: string;
  role: { id: string; name: string; permissions: string[]; default_dashboard?: string | null } | null;
  unit_id: string | null;
  is_active: boolean;
  last_login_at: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Unit {
  id: string;
  unit_code: string;
  name: string;
  region: string | null;
  city: string | null;
  state: string | null;
  latitude: number | null;
  longitude: number | null;
  status: string;
}

export interface UnitOverviewItem {
  id: string;
  unit_code: string;
  name: string;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
  agents: number;
  events: number;
  alerts: number;
  risk: number;
  status: string;
}

export interface UnitStats {
  unit: Unit;
  agent_count: number;
  agents_online: number;
  event_count_24h: number;
  alert_count_24h: number;
  open_alert_count: number;
  risk_score: number;
}

export interface Agent {
  id: string;
  agent_id: string;
  unit_id: string;
  unit_name: string | null;
  hostname: string;
  ip_address: string | null;
  os_version: string | null;
  agent_version: string | null;
  status: string;
  last_seen_at: string | null;
  events_per_sec: number;
  cpu_usage: number;
  memory_usage: number;
  buffer_size: number;
  simulated: boolean;
  last_sync_status: string | null;
  is_enabled: boolean;
  created_at: string | null;
}

export interface NormalizedEvent {
  id: number;
  timestamp: string;
  unit_id: string | null;
  unit_name: string | null;
  agent_id: string | null;
  hostname: string | null;
  event_id: number;
  provider: string | null;
  category: string | null;
  action: string | null;
  username: string | null;
  source_ip: string | null;
  destination_ip: string | null;
  process_name: string | null;
  command_line: string | null;
  logon_type: string | null;
  status_code: string | null;
  severity: string;
  is_suspicious: boolean;
  matched_rule_id: string | null;
  extra: Record<string, unknown> | null;
}

export interface EventDetail extends NormalizedEvent {
  parser_version: string | null;
  raw_log: string | null;
  log_id: number | null;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Paginated<T> {
  items: T[];
  meta: PageMeta;
}

export interface Alert {
  id: string;
  alert_id: string;
  rule_id: string | null;
  rule_name: string | null;
  title: string;
  description: string | null;
  severity: string;
  unit_id: string | null;
  unit_name: string | null;
  agent_id: string | null;
  hostname: string | null;
  source_ip: string | null;
  username: string | null;
  event_count: number;
  first_seen: string;
  last_seen: string;
  status: string;
  risk_score: number;
  risk_factors: { label: string; points: number }[] | null;
  mitre_technique: string | null;
  mitre_name: string | null;
  detection_explanation: string | null;
  recommended_steps: string[] | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AlertDetail extends Alert {
  events: NormalizedEvent[];
}

export interface Rule {
  id: string;
  rule_id: string;
  name: string;
  description: string | null;
  category: string;
  severity: string;
  event_id: number[];
  conditions: Record<string, unknown>;
  correlation_type: string;
  threshold: number;
  time_window_seconds: number;
  correlation_key: string | null;
  mitre_technique: string | null;
  mitre_name: string | null;
  status: string;
  times_matched: number;
  last_matched_at: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RuleTestResult {
  matched: boolean;
  reason: string;
  will_create_alert: boolean;
  details: Record<string, unknown> | null;
}

export interface AuditLog {
  id: number;
  user_id: string | null;
  username: string | null;
  action: string;
  category: string;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  user_id: string;
  type: string;
  severity: string;
  title: string;
  message: string | null;
  alert_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface KpiValue {
  label: string;
  value: number | string;
  change_pct: number | null;
  compare_label: string | null;
  detail: string | null;
  status: string | null;
}

export interface TimelinePoint {
  bucket: string;
  events: number;
  alerts: number;
  critical_alerts: number;
}

export interface SeverityBucket {
  severity: string;
  count: number;
  pct: number;
}

export interface LiveEventItem {
  id: number | null;
  timestamp: string;
  unit_id: string | null;
  unit_name: string | null;
  hostname: string | null;
  event_id: number;
  category: string | null;
  action: string | null;
  severity: string;
  source_ip: string | null;
  username: string | null;
  matched_rule_id: string | null;
  matched_rule_name: string | null;
  simulated: boolean;
}

export interface ActiveThreat {
  id: string;
  alert_id: string;
  title: string;
  severity: string;
  hostname: string | null;
  event_count: number;
  source_ip: string | null;
  username: string | null;
  event_id: number | null;
  detected_at: string;
  risk_score: number;
  status: string;
}

export interface AgentHealthItem {
  id: string;
  agent_id: string;
  hostname: string;
  unit_name: string | null;
  ip_address: string | null;
  os_version: string | null;
  last_seen_at: string | null;
  events_per_sec: number;
  cpu_usage: number;
  memory_usage: number;
  simulated: boolean;
  status: string;
}

export interface DashboardSummary {
  total_events: KpiValue;
  critical_alerts: KpiValue;
  high_alerts: KpiValue;
  active_agents: KpiValue;
  monitored_units: KpiValue;
  risk_score: KpiValue;
  timeline: TimelinePoint[];
  severity: SeverityBucket[];
  live_events: LiveEventItem[];
  active_threats: ActiveThreat[];
  units: UnitOverviewItem[];
  agent_health: AgentHealthItem[];
  top_rules: { rule_id: string; name: string; severity: string; times_matched: number; mitre_technique: string | null }[];
  generated_at: string;
}

export interface Stats {
  total_events: number;
  total_alerts: number;
  open_alerts: number;
  total_agents: number;
  agents_online: number;
  total_units: number;
  total_rules: number;
  events_per_second: number;
  storage_estimate_mb: number;
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  default_dashboard?: string | null;
}

export interface GraphOverview {
  backend: string;
  nodes: number;
  edges: number;
  entity_types: Record<string, number>;
}

export interface GraphNodeItem {
  id: string;
  entity_type: string;
  value: string;
  name: string;
  properties?: Record<string, unknown>;
  degree?: number | null;
}

export interface GraphEdgeItem {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface GraphRelationships {
  nodes: Record<string, GraphNodeItem>;
  edges: GraphEdgeItem[];
}

export interface GraphCommunity {
  id: string;
  size: number;
  entities: GraphNodeItem[];
}

export interface Incident {
  id: string;
  incident_id: string;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  category: string | null;
  source: string | null;
  unit_id: string | null;
  unit_name: string | null;
  hostname: string | null;
  source_ip: string | null;
  username: string | null;
  mitre_technique: string | null;
  mitre_name: string | null;
  alert_count: number;
  event_count: number;
  risk_score: number;
  assigned_to: string | null;
  created_by: string | null;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface IncidentNote {
  id: number;
  incident_id: string;
  user_id: string | null;
  username: string;
  content: string;
  timestamp: string;
  created_at: string | null;
}

export interface IncidentDetail extends Incident {
  alerts: Alert[];
  notes: IncidentNote[];
}

export interface IocEntry {
  id: string;
  ioc_id: string;
  ioc_type: "ip" | "domain" | "hash" | "url" | "command";
  value: string;
  description: string | null;
  source: string;
  severity: string;
  threat_type: string | null;
  reference_url: string | null;
  status: string;
  times_matched: number;
  last_matched_at: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MitreTechnique {
  technique: string;
  name: string | null;
  sub: string | null;
  rules: number;
  alerts: number;
  open_alerts: number;
  max_severity: string | null;
}

export interface TopIndicator {
  value: string;
  count: number;
}

export interface AnalyticsTop {
  top_source_ips: TopIndicator[];
  top_usernames: TopIndicator[];
  top_hosts: TopIndicator[];
  top_alert_rules: TopIndicator[];
}

export interface AlertByRule {
  rule_id: string;
  rule_name: string;
  severity: string;
  count: number;
}

export interface AlertByTechnique {
  technique: string;
  name: string | null;
  count: number;
}

export interface ThreatActivity {
  alerts_by_rule: AlertByRule[];
  alerts_by_technique: AlertByTechnique[];
}

export interface AgentEventItem {
  id: number;
  timestamp: string;
  hostname: string | null;
  event_id: number;
  provider: string | null;
  category: string | null;
  action: string | null;
  severity: string;
  username: string | null;
  source_ip: string | null;
  matched_rule_id: string | null;
  is_suspicious: boolean;
}

export interface IncidentEventItem {
  id: number;
  timestamp: string;
  hostname: string | null;
  event_id: number;
  category: string | null;
  action: string | null;
  severity: string;
  username: string | null;
  source_ip: string | null;
  process_name: string | null;
  command_line: string | null;
  matched_rule_id: string | null;
}

export interface AssetItem {
  hostname: string;
  unit_id: string | null;
  unit_name: string | null;
  unit: string | null;
  ip_address: string | null;
  os_version: string | null;
  status: string;
  last_seen_at: string | null;
  events_per_sec: number;
  total_events: number;
  open_alerts: number;
  total_alerts: number;
  max_alert_severity: string | null;
  risk_score: number;
}

export interface SearchResults {
  q: string;
  events: { id: number; timestamp: string; hostname: string | null; event_id: number; category: string | null; severity: string; username: string | null; source_ip: string | null }[];
  alerts: { id: string; alert_id: string; title: string; severity: string; status: string; hostname: string | null; source_ip: string | null; created_at: string | null }[];
  incidents: { id: string; incident_id: string; title: string; severity: string; status: string; hostname: string | null; created_at: string | null }[];
  rules: { id: string; rule_id: string; name: string; severity: string; times_matched: number }[];
  iocs: { id: string; ioc_id: string; ioc_type: string; value: string; severity: string }[];
  agents: { id: string; agent_id: string; hostname: string; ip_address: string | null; status: string }[];
  units: { id: string; unit_code: string; name: string; status: string }[];
}
