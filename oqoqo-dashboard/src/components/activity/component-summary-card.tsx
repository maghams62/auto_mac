"use client";

import { useMemo, type ReactNode } from "react";
import { Activity, ActivitySquare, CircleDot, Flame } from "lucide-react";
import { Pie, PieChart, ResponsiveContainer, Cell, Tooltip as RechartsTooltip } from "recharts";

import type { ActivityComponent, SignalSlice } from "@/lib/hooks/use-activity-drift-view";
import { buildSignalBreakdown, describeComponentRisk } from "@/lib/hooks/use-activity-drift-view";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ComponentSummaryCardProps {
  component: ActivityComponent | null;
}

export function ComponentSummaryCard({ component }: ComponentSummaryCardProps) {
  const breakdown = useMemo<SignalSlice[]>(() => {
    if (!component) return [];
    return buildSignalBreakdown(component);
  }, [component]);

  if (!component) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Why this component is risky</CardTitle>
          <CardDescription>Select a node in the system map to inspect its drift.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const summary = describeComponentRisk(component);

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2">
          {component.name}
          <Badge variant="secondary" className="rounded-full text-[10px] uppercase tracking-wide">
            Drift {component.driftScore.toFixed(1)}
          </Badge>
        </CardTitle>
        <CardDescription>{summary}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="Activity score" value={component.activityScore.toFixed(1)} icon={<Activity className="h-4 w-4 text-sky-400" />} />
          <Metric
            label="Change velocity"
            value={component.changeVelocity.toFixed(1)}
            icon={<ActivitySquare className="h-4 w-4 text-emerald-400" />}
          />
          <Metric label="Blast radius" value={component.blastRadius} icon={<CircleDot className="h-4 w-4 text-orange-300" />} />
          <Metric
            label="Open doc issues"
            value={component.docIssues.length}
            icon={<Flame className="h-4 w-4 text-rose-400" />}
          />
        </div>
        <div className="rounded-2xl border border-border/60 bg-muted/10 p-4">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Where drift pressure comes from</p>
          {breakdown.length ? (
            <div className="flex flex-col gap-4 md:flex-row md:items-center">
              <div className="h-40 w-full md:w-1/2">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={breakdown} dataKey="value" nameKey="label" innerRadius={45} outerRadius={70} paddingAngle={4}>
                      {breakdown.map((slice) => (
                        <Cell key={slice.key} fill={slice.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip formatter={(value: number, label: string) => [`${value.toFixed(1)}`, label]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-1 flex-col gap-2 text-sm">
                {breakdown.map((slice) => (
                  <div key={slice.key} className="flex items-center justify-between rounded-xl border border-border/40 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: slice.color }} />
                      <span>{slice.label}</span>
                    </div>
                    <span className="font-semibold text-foreground">{slice.value.toFixed ? slice.value.toFixed(1) : slice.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">No recent signals to chart for this component.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/50 bg-background/40 p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        {icon}
      </div>
      <p className="text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

