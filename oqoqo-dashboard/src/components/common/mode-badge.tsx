import type { LiveMode } from "@/lib/types";
import { cn } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";

type ModeBadgeProps = {
  mode?: LiveMode;
  fallback?: boolean;
  className?: string;
};

const MODE_LABEL: Record<LiveMode, string> = {
  atlas: "Live data",
  hybrid: "Hybrid data",
  synthetic: "Synthetic data",
  error: "Data unavailable",
};

export function ModeBadge({ mode = "synthetic", fallback, className }: ModeBadgeProps) {
  const label = fallback ? "Synthetic fallback" : MODE_LABEL[mode] ?? "Synthetic data";
  const tone =
    mode === "atlas" && !fallback
      ? "border-emerald-400/60 text-emerald-200"
      : mode === "error"
      ? "border-amber-400/60 text-amber-200"
      : "border-border/60 text-muted-foreground";

  return (
    <Badge
      variant="outline"
      className={cn("rounded-full px-3 py-1 text-[10px] uppercase tracking-wide", tone, className)}
      data-testid="mode-badge"
    >
      {label}
    </Badge>
  );
}


