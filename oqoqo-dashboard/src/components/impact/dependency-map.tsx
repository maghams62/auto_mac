import { DependencyEdge, ComponentNode } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

interface DependencyMapProps {
  dependencies: DependencyEdge[];
  components: ComponentNode[];
}

export function DependencyMap({ dependencies, components }: DependencyMapProps) {
  if (!dependencies.length) {
    return <div className="rounded-2xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">No cross-service edges defined yet.</div>;
  }

  const componentLookup = Object.fromEntries(components.map((component) => [component.id, component]));

  const grouped = dependencies.reduce<Record<string, DependencyEdge[]>>((acc, dependency) => {
    acc[dependency.sourceComponentId] = acc[dependency.sourceComponentId] ?? [];
    acc[dependency.sourceComponentId].push(dependency);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([sourceId, edges]) => {
        const source = componentLookup[sourceId];
        return (
          <div key={sourceId} className="rounded-3xl border border-border/60 bg-card/60 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-foreground">{source?.name ?? sourceId}</span>
              <Badge variant="outline" className="rounded-full border-border/60 text-xs">
                {source?.serviceType ?? "component"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">Upstream</p>
            <div className="mt-3 space-y-2">
              {edges.map((edge) => {
                const downstream = componentLookup[edge.targetComponentId];
                return (
                  <div key={edge.id} className="rounded-2xl border border-border/40 bg-muted/5 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">{downstream?.name ?? edge.targetComponentId}</span>
                      <Badge variant="outline" className="rounded-full border-border/40 text-xs">
                        {edge.surface.toUpperCase()}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{edge.description}</p>
                    <div className="flex flex-wrap gap-1 pt-2 text-xs text-muted-foreground">
                      {edge.contracts.map((contract) => (
                        <Badge key={contract} variant="outline" className="rounded-full border-border/30">
                          {contract}
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

