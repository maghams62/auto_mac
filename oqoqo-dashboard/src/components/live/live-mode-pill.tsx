"use client";

import { Badge } from "@/components/ui/badge";
import { useDashboardStore } from "@/lib/state/dashboard-store";

export function LiveModePill({ className }: { className?: string }) {
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  if (liveStatus.mode === "atlas") {
    return null;
  }

  if (liveStatus.mode === "error") {
    return (
      <Badge
        variant="outline"
        className={`rounded-full border-amber-400/60 text-xs text-amber-200 ${className ?? ""}`}
      >
        {liveStatus.message ? `Live ingest error: ${liveStatus.message}` : "Live ingest error"}
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={`rounded-full border-border/60 text-xs text-muted-foreground ${className ?? ""}`}
    >
      {liveStatus.mode === "hybrid" ? "Hybrid ingest mode" : "Synthetic dataset mode"}
    </Badge>
  );
}

