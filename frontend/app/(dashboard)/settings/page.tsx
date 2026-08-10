"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { KeyRound, Save, ShieldCheck } from "lucide-react";
import { authService, statsService } from "@/services";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageError } from "@/components/shared/page-states";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { formatNumber, cn } from "@/lib/utils";

export default function SettingsPage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "error"; text: string } | null>(null);

  const { data: stats, isError, error, refetch } = useQuery({
    queryKey: ["stats"],
    queryFn: () => statsService.get(),
    refetchInterval: 30000,
  });

  async function changePassword() {
    setMessage(null);
    if (newPassword !== confirmPassword) {
      setMessage({ type: "error", text: "New passwords do not match." });
      return;
    }
    if (newPassword.length < 8) {
      setMessage({ type: "error", text: "New password must be at least 8 characters." });
      return;
    }
    setSaving(true);
    try {
      await authService.changePassword(currentPassword, newPassword);
      setMessage({ type: "ok", text: "Password changed successfully." });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setMessage({ type: "error", text: err instanceof ApiError ? err.message : "Failed to change password." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader title="Settings" description="Account security and platform status." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-accent" />
              Change Password
            </CardTitle>
            <CardDescription>Rotate your CyberRakshak credentials. All changes are audited.</CardDescription>
          </CardHeader>
          <CardContent>
            {user?.role?.name === "super_admin" && (
              <div className="mb-3 flex items-center gap-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-accent">
                <ShieldCheck className="h-4 w-4" />
                Signed in with elevated privileges (super_admin).
              </div>
            )}
            {message && (
              <div
                className={cn(
                  "mb-3 rounded-md border px-3 py-2 text-xs",
                  message.type === "ok" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-critical/30 bg-critical/10 text-critical",
                )}
              >
                {message.text}
              </div>
            )}
            <div className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="current">Current password</Label>
                <Input id="current" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} autoComplete="current-password" />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="new">New password</Label>
                  <Input id="new" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="confirm">Confirm new password</Label>
                  <Input id="confirm" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} autoComplete="new-password" />
                </div>
              </div>
              <div className="flex justify-end">
                <Button onClick={() => void changePassword()} disabled={saving}>
                  <Save className="h-4 w-4" />
                  {saving ? "Saving…" : "Update Password"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-1">
              <CardTitle>Account</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <Info label="Username" value={user?.username ?? "—"} mono />
                <Info label="Full name" value={user?.full_name ?? "—"} />
                <Info label="Email" value={user?.email ?? "—"} />
                <Info label="Role" value={user?.role?.name ?? "—"} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1">
              <CardTitle>Platform Status</CardTitle>
            </CardHeader>
            <CardContent>
              {isError && <PageError message={(error as Error)?.message} onRetry={() => refetch()} />}
              {stats && (
                <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
                  <Info label="Events stored" value={formatNumber(stats.total_events)} mono />
                  <Info label="Open alerts" value={formatNumber(stats.open_alerts)} mono />
                  <Info label="Agents online" value={`${stats.agents_online} / ${stats.total_agents}`} mono />
                  <Info label="Units" value={formatNumber(stats.total_units)} mono />
                  <Info label="Rules" value={formatNumber(stats.total_rules)} mono />
                  <Info label="Storage est." value={`${stats.storage_estimate_mb} MB`} mono />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className={cn("mt-0.5 text-sm text-foreground", mono && "font-mono")}>{value}</p>
    </div>
  );
}
