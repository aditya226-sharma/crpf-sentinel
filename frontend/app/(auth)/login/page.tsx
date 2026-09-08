"use client";

import { Suspense } from "react";
import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, KeyRound, Loader2, Lock, LockKeyhole, User } from "lucide-react";
import { Brand } from "@/components/layout/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function RadarVisualization() {
  return (
    <div className="relative mx-auto h-[420px] w-full max-w-[520px]">
      <div className="absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-500/10">
        <div className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-500/15" />
        <div className="absolute left-1/2 top-1/2 h-36 w-36 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-500/20" />
        <div className="absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-500/30" />
        <div className="absolute inset-0 overflow-hidden rounded-full">
          <div className="absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 animate-radar-sweep bg-[conic-gradient(from_0deg,rgba(34,211,238,0.12),transparent_60deg,transparent)]" />
        </div>
      </div>

      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="flex h-12 w-12 items-center justify-center rounded-md bg-gradient-to-br from-cyan-500 to-blue-600 shadow-glow">
          <LockKeyhole className="h-6 w-6 text-white" />
        </div>
      </div>

      {[
        { x: "18%", y: "22%", c: "bg-emerald-400", p: "animate-pulse-dot" },
        { x: "74%", y: "16%", c: "bg-cyan-400", p: "animate-pulse-dot" },
        { x: "12%", y: "64%", c: "bg-cyan-400", p: "animate-pulse-dot" },
        { x: "82%", y: "70%", c: "bg-red-500", p: "" },
        { x: "50%", y: "8%", c: "bg-emerald-400", p: "" },
        { x: "88%", y: "38%", c: "bg-amber-400", p: "animate-pulse-dot" },
        { x: "30%", y: "88%", c: "bg-slate-500", p: "" },
      ].map((n, i) => (
        <span
          key={i}
          className={`absolute h-2 w-2 rounded-full ${n.c} ${n.p}`}
          style={{ left: n.x, top: n.y, boxShadow: "0 0 10px currentColor" }}
        />
      ))}
    </div>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = searchParams.get("from");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password, rememberMe);
      const fromParam = searchParams.get("from");
      const fromValid =
        fromParam && fromParam.startsWith("/") && !fromParam.startsWith("//");
      const roleTarget = "/dashboard";
      router.replace(fromValid ? fromParam : roleTarget);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Unable to sign in. Check your credentials.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden border-r border-border bg-surface3 p-12 lg:flex">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(34,211,238,0.10),transparent_55%)]" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(59,130,246,0.08),transparent_55%)]" />
        <div className="scanline-bg pointer-events-none absolute inset-0" />

        <div className="relative">
          <Brand />
        </div>

        <div className="relative">
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-foreground">
            Centralized Security Operations
          </h1>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-slate-400">
            Centralized visibility and threat detection across distributed CRPF IT infrastructure.
          </p>
        </div>

        <div className="relative">
          <RadarVisualization />
          <div className="mt-2 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-md border border-border bg-surface/70 px-3 py-2.5">
              <p className="font-mono text-lg font-semibold text-cyan-300">24/7</p>
              <p className="text-[10px] uppercase tracking-wider text-muted">Continuous Monitoring</p>
            </div>
            <div className="rounded-md border border-border bg-surface/70 px-3 py-2.5">
              <p className="font-mono text-lg font-semibold text-cyan-300">REAL-TIME</p>
              <p className="text-[10px] uppercase tracking-wider text-muted">Event Streaming</p>
            </div>
            <div className="rounded-md border border-border bg-surface/70 px-3 py-2.5">
              <p className="font-mono text-lg font-semibold text-cyan-300">SIEM</p>
              <p className="text-[10px] uppercase tracking-wider text-muted">Detection & Response</p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex w-full flex-col items-center justify-center px-4 py-12 lg:max-w-[520px]">
        <div className="mb-8 flex lg:hidden">
          <Brand />
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-foreground">Authorized Access Only</h2>
            <p className="mt-1 text-sm text-muted">
              Sign in with your CyberRakshak credentials. All access is audited.
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-md border border-critical/30 bg-critical/10 px-3 py-2 text-xs text-critical">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <div className="relative">
                <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  autoComplete="username"
                  required
                  className="pl-9"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <button type="button" className="text-[11px] text-accent hover:underline">
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                  className="pl-9 pr-9"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Switch checked={rememberMe} onCheckedChange={setRememberMe} id="remember" />
                <Label htmlFor="remember" className="cursor-pointer text-[11px]">
                  Remember me
                </Label>
              </div>
            </div>

            <Button type="submit" disabled={submitting} className="w-full" size="lg">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              {submitting ? "Authenticating…" : "Sign In"}
            </Button>
          </form>

          <div className="mt-6 flex items-center justify-center gap-4 text-[10px] uppercase tracking-[0.2em] text-slate-600">
            <span className="flex items-center gap-1.5">
              <LockKeyhole className="h-3 w-3" /> TLS Protected
            </span>
            <span className="h-3 w-px bg-slate-700" />
            <span>Authorized Personnel Only</span>
          </div>
        </div>

        <p className="mt-10 text-center text-[10px] uppercase tracking-[0.25em] text-slate-600">
          CyberRakshak · Restricted Network
        </p>
      </div>
    </div>
  );
}
