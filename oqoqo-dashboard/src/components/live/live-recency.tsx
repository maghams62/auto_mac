"use client";

import { formatDistanceToNow } from "date-fns";

import { cn } from "@/lib/utils";
import { isLiveLike } from "@/lib/mode";
import { useDashboardStore } from "@/lib/state/dashboard-store";

interface LiveRecencyProps {
  prefix?: string;
  className?: string;
}

export function LiveRecency({ prefix = "Signals updated", className }: LiveRecencyProps) {
  const liveStatus = useDashboardStore((state) => state.liveStatus);

  if (isLiveLike(liveStatus.mode) && liveStatus.lastUpdated) {
    const relative = formatDistanceToNow(new Date(liveStatus.lastUpdated), { addSuffix: true });
    return <span className={cn("text-xs text-muted-foreground", className)}>{`${prefix} ${relative}`}</span>;
  }

  if (liveStatus.mode === "error") {
    return (
      <span className={cn("text-xs text-amber-300", className)}>
        Live ingest unavailable{liveStatus.message ? `: ${liveStatus.message}` : ""}
      </span>
    );
  }

  return <span className={cn("text-xs text-muted-foreground", className)}>Live data disabled (synthetic fixtures)</span>;
}

