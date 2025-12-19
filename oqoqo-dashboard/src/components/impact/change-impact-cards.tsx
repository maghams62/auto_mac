import { ArrowRight, AlertTriangle } from "lucide-react";

import type { ChangeImpact, ComponentNode } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { shortDate } from "@/lib/utils";

interface ChangeImpactCardsProps {
  projectId: string;
  impacts: ChangeImpact[];
  components: ComponentNode[];
}

const severityColors: Record<string, string> = {
  critical: "bg-red-500/15 text-red-200 border-red-500/40",
  high: "bg-amber-500/15 text-amber-200 border-amber-500/40",
  medium: "bg-blue-500/15 text-blue-200 border-blue-500/40",
  low: "bg-emerald-500/15 text-emerald-200 border-emerald-500/40",
};

export function ChangeImpactCards({ projectId, impacts, components }: ChangeImpactCardsProps) {
  if (!impacts.length) {
    return <div className="rounded-2xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">No change events recorded yet.</div>;
  }

  const componentLookup = Object.fromEntries(components.map((component) => [component.id, component]));

  return (
    <div className="grid gap-4">
      {impacts.map((impact) => (
        <div key={impact.id} className="rounded-3xl border border-border/60 bg-card/60 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={`border text-xs ${severityColors[impact.severity] || ""}`}>{impact.severity}</Badge>
            <span className="text-xs text-muted-foreground">Changed {shortDate(impact.changedAt)}</span>
          </div>
          <div className="mt-2 text-lg font-semibold text-foreground">{impact.summary}</div>
          <p className="text-sm text-muted-foreground">{impact.description}</p>
          <div className="mt-3 rounded-2xl border border-border/40 bg-muted/10 p-3 text-sm">
            Upstream component:{" "}
            <strong>{componentLookup[impact.componentId]?.name ?? impact.componentId}</strong>
          </div>

          <div className="mt-4 space-y-3">
            {impact.downstream.map((node) => (
              <div key={`${impact.id}-${node.componentId}`} className="rounded-2xl border border-border/40 p-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  {componentLookup[node.componentId]?.name ?? node.componentId}
                  <Badge variant="outline" className="rounded-full border-border/40 text-xs uppercase">
                    {node.risk} risk
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{node.reason}</p>
                <div className="flex flex-wrap gap-1 pt-2 text-xs">
                  {node.docPaths.map((doc) => (
                    <Badge key={doc} variant="outline" className="rounded-full border-border/30">
                      {doc}
                    </Badge>
                  ))}
                </div>
                <Button variant="ghost" size="sm" className="mt-3 rounded-full text-xs" asChild>
                  <a href={`/projects/${projectId}/components/${node.componentId}`}>
                    Inspect component
                    <ArrowRight className="ml-1 h-4 w-4" />
                  </a>
                </Button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

