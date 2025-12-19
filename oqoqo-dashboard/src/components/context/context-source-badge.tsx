"use client";

import { Badge } from "@/components/ui/badge";
import type { ContextResponse } from "@/lib/context/types";

const providerLabels: Record<ContextResponse["provider"], string> = {
  synthetic: "synthetic demo",
  qdrant: "Qdrant live",
};

export function ContextSourceBadge({ response }: { response: ContextResponse }) {
  const label = providerLabels[response.provider] ?? response.provider;
  const text = response.fallback ? `Context source • ${label} (fallback)` : `Context source • ${label}`;
  return (
    <Badge variant="outline" className="rounded-full border-border/60 px-3 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
      {text}
    </Badge>
  );
}

