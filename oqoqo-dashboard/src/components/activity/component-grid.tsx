import Link from "next/link";
import { ArrowRight, Flame, Layers3, Radar } from "lucide-react";

import type { ComponentNode } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { signalSourceTokens } from "@/lib/ui/tokens";
import { shortDate } from "@/lib/utils";

interface ComponentGridProps {
  projectId: string;
  components: ComponentNode[];
}

export function ComponentGrid({ projectId, components }: ComponentGridProps) {
  return (
    <div className="grid gap-4">
      {components.map((component) => (
        <div
          key={component.id}
          className="grid gap-4 rounded-3xl border border-border/60 bg-card/70 p-5 transition hover:border-primary/40 md:grid-cols-[2fr,1fr]"
        >
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold text-foreground">{component.name}</h3>
              <Badge variant="outline" className="rounded-full border-border/60">
                {component.serviceType}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">{component.graphSignals.activity.summary}</p>
            <div className="flex flex-wrap gap-2">
              {component.tags.map((tag) => (
                <Badge key={tag} variant="outline" className="rounded-full border-border/40 text-xs">
                  {tag}
                </Badge>
              ))}
              {component.divergenceInsights.length ? (
                <Badge variant="outline" className="rounded-full border-amber-500/40 bg-amber-500/10 text-[11px] text-amber-200">
                  {component.divergenceInsights.length} divergence alert
                  {component.divergenceInsights.length > 1 ? "s" : ""}
                </Badge>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-4 pt-2 text-sm">
              <SignalPill icon={Flame} label="Activity" value={component.graphSignals.activity.score} />
              <SignalPill icon={Radar} label="Drift" value={component.graphSignals.drift.score} />
              <SignalPill icon={Layers3} label="Dissatisfaction" value={component.graphSignals.dissatisfaction.score} />
            </div>
            <LatestSignal component={component} />
          </div>
          <div className="flex flex-col items-end justify-between gap-3 rounded-2xl border border-border/50 p-4 text-right text-sm text-muted-foreground">
            <div>
              <div>Docs monitored</div>
              <div className="font-semibold text-foreground">{component.docSections.length}</div>
            </div>
            <div>
              <div>Repositories</div>
              <div className="font-semibold text-foreground">{component.repoIds.length}</div>
            </div>
            <Button asChild variant="outline" className="mt-auto rounded-full">
              <Link href={`/projects/${projectId}/components/${component.id}`}>
                Inspect component
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

const SignalPill = ({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) => (
  <div className="inline-flex items-center gap-2 rounded-full border border-border/40 bg-muted/10 px-3 py-1 text-xs font-semibold text-muted-foreground">
    <Icon className="h-3.5 w-3.5 text-primary" />
    <span className="text-foreground">{value}</span>
    {label}
  </div>
);

const LatestSignal = ({ component }: { component: ComponentNode }) => {
  if (!component.sourceEvents.length) return null;
  const latest = component.sourceEvents.reduce((acc, curr) =>
    new Date(curr.timestamp).getTime() > new Date(acc.timestamp).getTime() ? curr : acc
  );
  const uniqueSources = Array.from(new Set(component.sourceEvents.map((event) => event.source)));

  return (
    <div className="mt-3 rounded-2xl border border-border/40 bg-muted/10 p-4 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">Latest signal</span>
        <span className="text-muted-foreground">{shortDate(latest.timestamp)}</span>
        <div className="flex flex-wrap gap-1">
          {uniqueSources.map((source) => {
            const token = signalSourceTokens[source];
            return (
              <Badge key={`${component.id}-${source}`} className={`border text-[10px] ${token.color}`}>
                {token.label}
              </Badge>
            );
          })}
        </div>
      </div>
      <div className="pt-2 text-sm font-semibold text-foreground">{latest.title}</div>
      <p className="text-xs text-muted-foreground">{latest.description}</p>
    </div>
  );
};

