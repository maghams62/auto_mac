"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { ArrowRight } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { ComponentNode } from "@/lib/types";

export default function ComponentDetailPage() {
  const params = useParams<{ projectId: string; componentId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const componentId = Array.isArray(params.componentId) ? params.componentId[0] : params.componentId;
  const projects = useDashboardStore((state) => state.projects);
  const project = projects.find((item) => item.id === projectId);
  const component = project?.components.find((item) => item.id === componentId);

  const componentIssues = useMemo(() => {
    if (!project || !component) return [];
    return project.docIssues.filter((issue) => issue.componentId === component.id);
  }, [project, component]);

  const dependencies = useMemo(() => {
    if (!project || !component) return [];
    return project.dependencies.filter(
      (dependency) => dependency.sourceComponentId === component.id || dependency.targetComponentId === component.id
    );
  }, [project, component]);

  if (!project || !component) {
    return <div className="text-sm text-destructive">Component not found.</div>;
  }

  const { activity, drift, dissatisfaction, timeline } = component.graphSignals;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="outline" className="rounded-full border-border/60">
            {component.serviceType}
          </Badge>
          <Badge variant="outline" className="rounded-full border-border/60">
            Team • {component.ownerTeam}
          </Badge>
        </div>
        <h1 className="text-3xl font-semibold text-foreground">{component.name}</h1>
        <p className="text-sm text-muted-foreground">{activity.summary}</p>
        <div className="flex flex-wrap gap-2">
          {component.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="rounded-full border-border/40 text-xs">
              {tag}
            </Badge>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Graph signals timeline</CardTitle>
          <CardDescription>Activity, drift, and dissatisfaction plotted across the last 2 weeks.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeline}>
                <defs>
                  <linearGradient id="activityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7dd3fc" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#7dd3fc" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="driftGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fca5a5" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#fca5a5" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="dissatisfactionGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fcd34d" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#fcd34d" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="timestamp" hide />
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="rounded-xl border border-border/60 bg-background/95 p-3 text-xs text-foreground">
                        <div className="font-semibold">{new Date(payload[0].payload.timestamp).toLocaleDateString()}</div>
                        {payload.map((entry) => (
                          <div key={entry.dataKey} className="flex items-center gap-2">
                            <span
                              className="h-2 w-2 rounded-full"
                              style={{ backgroundColor: entry.color }}
                            />
                            <span className="capitalize">
                              {entry.name}: {Math.round(entry.value as number)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null
                  }
                />
                <Area type="monotone" dataKey="activity" stroke="#7dd3fc" fillOpacity={1} fill="url(#activityGradient)" name="activity" />
                <Area type="monotone" dataKey="drift" stroke="#fca5a5" fillOpacity={1} fill="url(#driftGradient)" name="drift" />
                <Area
                  type="monotone"
                  dataKey="dissatisfaction"
                  stroke="#fcd34d"
                  fillOpacity={1}
                  fill="url(#dissatisfactionGradient)"
                  name="dissatisfaction"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="activity" className="rounded-3xl border border-border/60 bg-card/70 p-5">
        <TabsList className="bg-muted/30">
          <TabsTrigger value="activity">Activity</TabsTrigger>
          <TabsTrigger value="drift">Drift</TabsTrigger>
          <TabsTrigger value="dissatisfaction">Dissatisfaction</TabsTrigger>
        </TabsList>
        <TabsContent value="activity">
          <SignalDetails bundle={activity} />
        </TabsContent>
        <TabsContent value="drift">
          <SignalDetails bundle={drift} />
        </TabsContent>
        <TabsContent value="dissatisfaction">
          <SignalDetails bundle={dissatisfaction} />
        </TabsContent>
      </Tabs>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Linked docs & repos</CardTitle>
            <CardDescription>Source locations that will be auto-checked for drift.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {component.docSections.map((doc) => (
              <div key={doc} className="rounded-2xl border border-border/50 p-3 text-sm text-muted-foreground">
                {doc}
              </div>
            ))}
            <div className="text-xs text-muted-foreground">Repos: {component.repoIds.join(", ")}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Graph neighbors</CardTitle>
            <CardDescription>Cross-service dependencies detected by Oqoqo.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {dependencies.map((dependency) => (
              <div key={dependency.id} className="rounded-2xl border border-border/50 p-3 text-sm">
                <div className="font-semibold text-foreground">{dependency.surface.toUpperCase()}</div>
                <p className="text-xs text-muted-foreground">{dependency.description}</p>
                <div className="flex flex-wrap gap-1 pt-2 text-xs text-muted-foreground">
                  {dependency.contracts.map((contract) => (
                    <Badge key={contract} variant="outline" className="rounded-full border-border/40">
                      {contract}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
            {!dependencies.length ? (
              <div className="text-sm text-muted-foreground">No dependencies mapped yet.</div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Open doc drift issues</CardTitle>
          <CardDescription>Issues tied to this component feed dissatisfaction scoring.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {componentIssues.length ? (
            componentIssues.map((issue) => (
              <div key={issue.id} className="rounded-2xl border border-border/50 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold text-foreground">{issue.title}</div>
                    <p className="text-xs text-muted-foreground">{issue.summary}</p>
                  </div>
                  <Button variant="ghost" className="rounded-full text-xs" asChild>
                    <a href={`/projects/${project.id}/issues/${issue.id}`}>
                      Review issue
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </a>
                  </Button>
                </div>
                <div className="flex flex-wrap gap-3 pt-2 text-xs text-muted-foreground">
                  <span>
                    Severity • <strong>{issue.severity}</strong>
                  </span>
                  <span>
                    Status • <strong>{issue.status}</strong>
                  </span>
                  <span>
                    Doc • <strong>{issue.docPath}</strong>
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">No open issues for this component.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const SignalDetails = ({ bundle }: { bundle: ComponentNode["graphSignals"]["activity"] }) => (
  <div className="grid gap-6 md:grid-cols-2">
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Score</div>
      <div className="text-4xl font-bold text-foreground">{bundle.score}</div>
      <p className="text-xs text-muted-foreground">
        {bundle.summary} ({bundle.window} window, {bundle.trend} trend)
      </p>
    </div>
    <div className="space-y-3">
      {bundle.metrics.map((metric) => (
        <div key={metric.label} className="rounded-2xl border border-border/50 p-3 text-sm">
          <div className="flex items-center justify-between">
            <div className="text-muted-foreground">{metric.label}</div>
            <div className="font-semibold text-foreground">
              {metric.value} {metric.unit}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Δ {metric.delta}% — {metric.description}
          </p>
        </div>
      ))}
    </div>
  </div>
);

