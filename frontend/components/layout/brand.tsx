import { cn } from "@/lib/utils";

export function Brand({ className, collapsed }: { className?: string; collapsed?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", collapsed && "justify-center", className)}>
      <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-cyan-500 to-blue-600 shadow-glow">
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-white" aria-hidden>
          <path
            d="M12 3l7 3.5v5c0 4.4-3 8.1-7 9.5-4-1.4-7-5.1-7-9.5v-5L12 3z"
            fill="currentColor"
            fillOpacity="0.25"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M8.5 12l2.3 2.3L15.5 9.7"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      {!collapsed && (
        <div className="flex flex-col leading-none">
          <span className="text-sm font-bold tracking-widest text-foreground">
            Cyber<span className="text-accent">Rakshak</span>
          </span>
          <span className="text-[9px] font-medium uppercase tracking-[0.25em] text-muted">
            Security Operations
          </span>
        </div>
      )}
    </div>
  );
}
