"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldOff, ShieldCheck, Trash2, Copy, Check, Cpu, HardDrive } from "lucide-react";
import { agentService, unitService } from "@/services";
import type { Agent } from "@/types";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/shared/status-badge";
import { PageError, PageLoading, PageEmpty } from "@/components/shared/page-states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { timeAgo, cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

export default function AgentsPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("all");
  const [registering, setRegistering] = useState(false);

  const params = useMemo(() => ({ status: status === "all" ? undefined : status }), [status]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["agents", params],
    queryFn: () => agentService.list(params),
    refetchInterval: 15000,
  });

  async function toggleEnabled(agent: Agent) {
    await agentService.update(agent.id, { is_enabled: !agent.is_enabled });
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
  }

  async function revoke(agent: Agent) {
    if (!confirm(`Revoke agent ${agent.agent_id}? This cannot be undone.`)) return;
    await agentService.revoke(agent.id);
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
  }

  return (
    <div>
      <PageHeader
        title="Windows Agents"
        description="Endpoints streaming Windows Event Logs to CyberRakshak."
        actions={
          can("agents.manage") && (
            <Button size="sm" onClick={() => setRegistering(true)}>
              <Plus className="h-3.5 w-3.5" />
              Register Agent
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface p-3">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="online">Online</SelectItem>
            <SelectItem value="offline">Offline</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="disabled">Disabled</SelectItem>
          </SelectContent>
        </Select>
        <span className="ml-auto text-xs text-muted">
          {data?.length ?? 0} agents · auto-refreshing
        </span>
      </div>

      {isLoading && <PageLoading rows={12} />}
      {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}
      {data && data.length === 0 && <PageEmpty title="No agents registered" />}

      {data && data.length > 0 && (
        <div className="rounded-md border border-border bg-surface">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Host</TableHead>
                <TableHead>Agent ID</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead>OS</TableHead>
                <TableHead className="text-right">EPS</TableHead>
                <TableHead className="text-right">CPU</TableHead>
                <TableHead className="text-right">RAM</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Seen</TableHead>
                {can("agents.manage") && <TableHead className="text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((agent) => (
                <TableRow key={agent.id} className={cn(!agent.is_enabled && "opacity-50")}>
                  <TableCell>
                    <Link href={`/agents/${agent.id}`} className="group block min-w-0">
                      <span className="block text-xs font-medium text-foreground group-hover:text-accent">{agent.hostname}</span>
                      <span className="block font-mono text-[10px] text-muted">{agent.ip_address ?? "—"}</span>
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-accent">{agent.agent_id}</TableCell>
                  <TableCell className="text-xs text-muted">{agent.unit_name ?? "—"}</TableCell>
                  <TableCell className="font-mono text-[10px] text-slate-500">{agent.os_version ?? "—"}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{agent.events_per_sec}</TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    <Cpu className="mr-0.5 inline h-3 w-3 text-muted" />
                    {agent.cpu_usage.toFixed(0)}%
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    <HardDrive className="mr-0.5 inline h-3 w-3 text-muted" />
                    {agent.memory_usage.toFixed(0)}%
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusBadge status={agent.status} className="text-[9px]" />
                      {!agent.is_enabled && <Badge variant="default" className="text-[9px]">disabled</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-[11px] text-muted">{timeAgo(agent.last_seen_at)}</TableCell>
                  {can("agents.manage") && (
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="iconSm" title={agent.is_enabled ? "Disable" : "Enable"} onClick={() => void toggleEnabled(agent)}>
                          {agent.is_enabled ? <ShieldOff className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4 text-emerald-400" />}
                        </Button>
                        <Button variant="ghost" size="iconSm" title="Revoke" className="text-critical hover:text-critical" onClick={() => void revoke(agent)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {registering && (
        <RegisterAgentDialog
          onClose={() => setRegistering(false)}
          onRegistered={() => {
            setRegistering(false);
            void queryClient.invalidateQueries({ queryKey: ["agents"] });
          }}
        />
      )}
    </div>
  );
}

function RegisterAgentDialog({ onClose, onRegistered }: { onClose: () => void; onRegistered: () => void }) {
  const { data: units } = useQuery({ queryKey: ["units", "all"], queryFn: () => unitService.list() });
  const [agentId, setAgentId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [hostname, setHostname] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [osVersion, setOsVersion] = useState("Windows Server 2019");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ token: string; agent: Agent } | null>(null);

  async function register() {
    setError(null);
    setSaving(true);
    try {
      const res = await agentService.register({
        agent_id: agentId.trim(),
        unit_id: unitId,
        hostname: hostname.trim(),
        ip_address: ipAddress.trim() || null,
        os_version: osVersion.trim() || null,
      });
      setResult({ token: res.api_token, agent: res.agent });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register agent");
    } finally {
      setSaving(false);
    }
  }

  if (result) {
    return (
      <Modal onClose={onClose}>
        <h3 className="text-base font-semibold text-foreground">Agent Registered</h3>
        <p className="mt-1 text-xs text-muted">
          Copy the API token now — it is shown only once. Configure it in{" "}
          <code className="rounded bg-surface2 px-1 font-mono text-accent">agent/config/agent.yaml</code>.
        </p>
        <div className="mt-4 rounded-md border border-accent/30 bg-accent/5 p-3">
          <p className="text-[10px] uppercase tracking-wider text-muted">API Token</p>
          <TokenRow token={result.token} />
        </div>
        <div className="mt-5 flex justify-end">
          <Button onClick={onRegistered}>Done</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal onClose={onClose}>
      <h3 className="text-base font-semibold text-foreground">Register Windows Agent</h3>
      <p className="mt-1 text-xs text-muted">Generate credentials for a new log collector endpoint.</p>

      {error && <div className="mt-3 rounded-md border border-critical/30 bg-critical/10 px-3 py-2 text-xs text-critical">{error}</div>}

      <div className="mt-4 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="agent_id">Agent ID</Label>
            <Input id="agent_id" value={agentId} onChange={(e) => setAgentId(e.target.value)} placeholder="WIN-AGT-1001" className="font-mono" />
          </div>
          <div className="space-y-1">
            <Label>Unit</Label>
            <Select value={unitId} onValueChange={setUnitId}>
              <SelectTrigger><SelectValue placeholder="Select unit" /></SelectTrigger>
              <SelectContent>
                {units?.map((u) => (
                  <SelectItem key={u.id} value={u.id}>{u.unit_code} · {u.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="hostname">Hostname</Label>
            <Input id="hostname" value={hostname} onChange={(e) => setHostname(e.target.value)} placeholder="PC-01-0123" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ip">IP Address</Label>
            <Input id="ip" value={ipAddress} onChange={(e) => setIpAddress(e.target.value)} placeholder="10.0.1.23" className="font-mono" />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor="os">OS Version</Label>
            <Input id="os" value={osVersion} onChange={(e) => setOsVersion(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={() => void register()} disabled={saving || !agentId.trim() || !unitId}>
          {saving ? "Registering…" : "Register Agent"}
        </Button>
      </div>
    </Modal>
  );
}

function TokenRow({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-1 flex items-center gap-2">
      <code className="flex-1 overflow-x-auto rounded bg-background px-2 py-1.5 font-mono text-[11px] text-accent">{token}</code>
      <Button
        variant="ghost"
        size="iconSm"
        onClick={() => {
          void navigator.clipboard.writeText(token);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-md border border-border bg-surface p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
