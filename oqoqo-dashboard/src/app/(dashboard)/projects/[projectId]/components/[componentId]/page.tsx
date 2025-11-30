"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Activity, ArrowRight, FileText, GitCommit, LifeBuoy, MessageSquare, Ticket } from "lucide-react";

import { AskOqoqoCard } from "@/components/common/ask-oqoqo";
import { AskCerebrosButton } from "@/components/common/ask-cerebros-button";
import { fetchComponentActivity, isCerebrosApiConfigured, type ActivitySummary } from "@/lib/api/activity";
import { ContextSourceBadge } from "@/components/context/context-source-badge";
import { LiveRecency } from "@/components/live/live-recency";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import { filterIssuesWithContext } from "@/lib/issues/utils";
import { requestContextSnippets } from "@/lib/context/client";
import type { ContextResponse, ContextSnippet } from "@/lib/context/types";
import { selectComponentById, selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import type { ComponentNode, DocIssue, Severity, SignalSource, SourceEvent } from "@/lib/types";
import { severityTokens, signalSourceTokens } from "@/lib/ui/tokens";
import { longDateTime, shortDate } from "@/lib/utils";

const CEREBROS_APP_BASE = (process.env.NEXT_PUBLIC_CEREBROS_APP_BASE ?? "https://cerebros.example.com").replace(/\/$/, "");

function buildCerebrosUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${CEREBROS_APP_BASE}${normalizedPath}`;
}

export default function ComponentDetailPage() {
  const params = useParams<{ projectId: string; componentId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const componentId = Array.isArray(params.componentId) ? params.componentId[0] : params.componentId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const componentSelector = useMemo(() => selectComponentById(projectId, componentId), [projectId, componentId]);
  const project = useDashboardStore(projectSelector);
  const component = useDashboardStore(componentSelector);
  const selectComponent = useDashboardStore((state) => state.selectComponent);
  const filters = useDashboardStore((state) => state.issueFilters);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const [activitySummary, setActivitySummary] = useState<ActivitySummary | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  const activityEnabled = isCerebrosApiConfigured();
  const referenceTime = liveStatus.lastUpdated ? new Date(liveStatus.lastUpdated).getTime() : null;
  const [contextResponse, setContextResponse] = useState<ContextResponse | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState<string | null>(null);

  useEffect(() => {
    if (componentId) {
      selectComponent(componentId);
    }

    return () => selectComponent(undefined);
  }, [componentId, selectComponent]);

  useEffect(() => {
    if (!activityEnabled || !component) {
      setActivitySummary(null);
      setActivityError(null);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        setActivityLoading(true);
        const result = await fetchComponentActivity(component.id);
        if (!cancelled) {
          setActivitySummary(result);
          setActivityError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setActivityError(error instanceof Error ? error.message : "Failed to load activity");
        }
      } finally {
        if (!cancelled) {
          setActivityLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [activityEnabled, component]);

  useEffect(() => {
    if (!component) {
      setContextResponse(null);
      return;
    }
    let cancelled = false;
    setContextLoading(true);
    setContextError(null);
    requestContextSnippets({ projectId, componentId: component.id })
      .then((response) => {
        if (!cancelled) {
          setContextResponse(response);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setContextResponse(null);
          setContextError(error instanceof Error ? error.message : "Failed to load context");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setContextLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [component, projectId]);

  const filteredComponentIssues = useMemo(() => {
    if (!project || !component) return [];
    const scopedIssues = filterIssuesWithContext(project, filters, referenceTime);
    return scopedIssues.filter((issue) => issue.componentId === component.id);
  }, [project, component, filters, referenceTime]);
  const liveComponentIssues = useMemo(
    () => filteredComponentIssues.filter((issue) => issue.id.startsWith("live_issue")),
    [filteredComponentIssues]
  );
  const liveIssuesMeta = useMemo(() => {
    if (!liveComponentIssues.length) return null;
    const counts: Record<Severity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };
    let lastUpdated = 0;
    liveComponentIssues.forEach((issue) => {
      counts[issue.severity] += 1;
      const ts = new Date(issue.updatedAt).getTime();
      if (ts > lastUpdated) {
        lastUpdated = ts;
      }
    });
    return {
      counts,
      lastUpdated,
    };
  }, [liveComponentIssues]);

  const dependencies = useMemo(() => {
    if (!project || !component) return [];
    return project.dependencies.filter(
      (dependency) => dependency.sourceComponentId === component.id || dependency.targetComponentId === component.id
    );
  }, [project, component]);

  const contextGroups = useMemo(() => {
    if (!contextResponse) return [];
    const grouped = contextResponse.snippets.reduce<Record<ContextSnippet["source"], ContextSnippet[]>>((acc, snippet) => {
      acc[snippet.source] = acc[snippet.source] ?? [];
      acc[snippet.source].push(snippet);
      return acc;
    }, {} as Record<ContextSnippet["source"], ContextSnippet[]>);
    return Object.entries(grouped);
  }, [contextResponse]);

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
        <LiveRecency prefix="Live signals updated" />
      </div>

      <Card className="border border-primary/30 bg-primary/5">
        <CardHeader className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Live drift issues</CardTitle>
            <CardDescription>Real-time heuristics for this component.</CardDescription>
          </div>
          {liveIssuesMeta ? (
            <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase text-muted-foreground">
              Updated {shortDate(new Date(liveIssuesMeta.lastUpdated).toISOString())}
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3">
          {liveIssuesMeta ? (
            <>
              <div className="flex flex-wrap gap-2 text-xs">
                {(Object.keys(liveIssuesMeta.counts) as Severity[])
                  .filter((severity) => liveIssuesMeta.counts[severity] > 0)
                  .map((severity) => {
                    const token = severityTokens[severity];
                    return (
                      <Badge key={severity} className={`border text-[10px] ${token.color}`}>
                        {token.label}: {liveIssuesMeta.counts[severity]}
                      </Badge>
                    );
                  })}
              </div>
              <div className="space-y-2">
                {liveComponentIssues.map((issue) => (
                  <ComponentLiveIssueRow
                    key={issue.id}
                    projectId={project.id}
                    issue={issue}
                    component={component}
                    onOpen={() => setSelectedIssue(issue)}
                  />
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No live drift issues detected for this component.</p>
          )}
        </CardContent>
      </Card>

      {activityEnabled ? (
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-primary" />
                Cerebros activity
              </CardTitle>
              <CardDescription>
                Aggregated over {activitySummary?.windowDays ?? 14} days of doc-drift telemetry.
              </CardDescription>
            </div>
            <AskCerebrosButton command={`/slack docdrift ${component.name}`} label="Copy /slack docdrift" />
          </CardHeader>
          <CardContent>
            {activityLoading ? (
              <p className="text-sm text-muted-foreground">Fetching latest activity…</p>
            ) : activityError ? (
              <p className="text-sm text-destructive">{activityError}</p>
            ) : activitySummary ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <ActivityStat label="Activity score" value={activitySummary.activityScore.toFixed(2)} />
                <ActivityStat label="Doc drift events" value={`${activitySummary.docDriftEvents}`} />
                <ActivityStat label="Slack events" value={`${activitySummary.slackEvents}`} />
                <ActivityStat label="Git events" value={`${activitySummary.gitEvents}`} />
                <ActivityStat
                  label="Last event"
                  value={
                    activitySummary.lastEventAt
                      ? longDateTime(activitySummary.lastEventAt)
                      : "N/A"
                  }
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No Cerebros telemetry available yet.</p>
            )}
          </CardContent>
        </Card>
      ) : null}

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
                        <div className="font-semibold">{shortDate(payload[0].payload.timestamp)}</div>
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

      <Tabs defaultValue="overview" className="rounded-3xl border border-border/60 bg-card/70 p-5">
        <TabsList className="flex-wrap bg-muted/30">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="git">Git</TabsTrigger>
          <TabsTrigger value="docs">Docs</TabsTrigger>
          <TabsTrigger value="slack">Slack</TabsTrigger>
          <TabsTrigger value="tickets">Tickets</TabsTrigger>
          <TabsTrigger value="support">Support</TabsTrigger>
          <TabsTrigger value="context">Context</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <div className="grid gap-4 md:grid-cols-3">
            <OverviewSignal label="Activity" bundle={activity} />
            <OverviewSignal label="Drift" bundle={drift} />
            <OverviewSignal label="Dissatisfaction" bundle={dissatisfaction} />
          </div>
        </TabsContent>
        {(["git", "docs", "slack", "tickets", "support"] as SignalSource[]).map((source) => (
          <TabsContent key={source} value={source}>
            <SourceEventList
              events={component.sourceEvents.filter((event) => event.source === source)}
              emptyLabel={`No ${source} signals recorded for this component.`}
            />
          </TabsContent>
        ))}
        <TabsContent value="context" id="context">
          <div className="space-y-3">
            {contextResponse ? (
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <ContextSourceBadge response={contextResponse} />
                <span>{contextResponse.snippets.length} snippets indexed</span>
              </div>
            ) : null}
            {contextLoading ? (
              <p className="text-sm text-muted-foreground">Loading context…</p>
            ) : contextError ? (
              <p className="text-sm text-muted-foreground">{contextError}</p>
            ) : contextGroups.length ? (
              contextGroups.map(([source, snippets]) => (
                <div key={source} className="rounded-2xl border border-border/40 p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    {contextSourceLabels[source as ContextSnippet["source"]] ?? source} • {snippets.length}
                  </p>
                  <ul className="space-y-2 pt-2 text-sm text-muted-foreground">
                    {snippets.slice(0, 3).map((snippet) => (
                      <li key={snippet.id} className="flex flex-col gap-1">
                        <span className="text-foreground">{snippet.summary}</span>
                        <div className="flex flex-wrap items-center gap-2 text-[11px]">
                          <a
                            href={snippet.link}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary underline-offset-2 hover:underline"
                          >
                            Open source
                          </a>
                          <span>{Math.round(snippet.confidence * 100)}% confident</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No semantic context available for this component.</p>
            )}
            <Button variant="outline" className="rounded-full text-xs" asChild>
              <a href={buildCerebrosUrl(`/projects/${projectId}/components/${component.id}`)} target="_blank" rel="noreferrer">
                View detailed reasoning in Cerebros
              </a>
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>Cross-system divergence</CardTitle>
          <CardDescription>Where underlying sources disagree for this component.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {component.divergenceInsights.length ? (
            component.divergenceInsights.map((insight) => (
              <div key={insight.id} className="rounded-2xl border border-border/40 p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge
                    variant="outline"
                    className={`rounded-full border-border/60 text-[10px] ${
                      insight.severity === "critical"
                        ? "bg-red-500/15 text-red-200 border-red-500/40"
                        : insight.severity === "high"
                        ? "bg-amber-500/15 text-amber-200 border-amber-500/40"
                        : insight.severity === "medium"
                        ? "bg-blue-500/15 text-blue-100 border-blue-500/40"
                        : "bg-emerald-500/15 text-emerald-100 border-emerald-500/40"
                    }`}
                  >
                    {insight.severity.toUpperCase()}
                  </Badge>
                  <span className="text-muted-foreground">Detected {shortDate(insight.detectedAt)}</span>
                </div>
                <p className="pt-2 text-sm text-muted-foreground">{insight.summary}</p>
                <div className="flex flex-wrap gap-2 pt-2">
                  {insight.sources.map((source) => {
                    const token = signalSourceTokens[source];
                    return (
                      <Badge key={`${insight.id}-${source}`} className={`border text-[10px] ${token.color}`}>
                        {token.label}
                      </Badge>
                    );
                  })}
                </div>
                {insight.affectedDocs.length ? (
                  <div className="pt-2 text-xs text-muted-foreground">
                    Docs:{' '}
                    <span className="font-medium text-foreground">{insight.affectedDocs.join(", ")}</span>
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">No divergence alerts logged for this component.</div>
          )}
        </CardContent>
      </Card>

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
          {filteredComponentIssues.length ? (
            filteredComponentIssues.map((issue) => (
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

      <AskOqoqoCard
        context="component"
        title={component.name}
        summary={`Drift score ${component.graphSignals.drift.score}: ${component.graphSignals.drift.summary}`}
      />
    </div>
  );
}

const OverviewSignal = ({ label, bundle }: { label: string; bundle: ComponentNode["graphSignals"]["activity"] }) => (
  <div className="rounded-2xl border border-border/60 p-4">
    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="text-3xl font-bold text-foreground">{bundle.score}</div>
    <p className="text-xs text-muted-foreground">
      {bundle.summary} ({bundle.window} • {bundle.trend})
    </p>
    <div className="pt-2 text-[11px] text-muted-foreground">
      {bundle.metrics[0]
        ? `Top metric: ${bundle.metrics[0].label} (${bundle.metrics[0].value} ${bundle.metrics[0].unit})`
        : "No supporting metrics yet."}
    </div>
  </div>
);

const SourceEventList = ({
  events,
  emptyLabel,
}: {
  events: ComponentNode["sourceEvents"];
  emptyLabel: string;
}) => {
  if (!events.length) {
    return <div className="text-sm text-muted-foreground">{emptyLabel}</div>;
  }

  return (
    <div className="space-y-3">
      {events.map((event) => {
        const Icon = sourceIconMap[event.source];
        const token = signalSourceTokens[event.source];
        return (
          <div key={event.id} className="rounded-2xl border border-border/40 p-4">
            <div className="flex items-start gap-3">
              <Icon className="mt-1 h-4 w-4 text-primary" />
              <div>
                <div className="text-sm font-semibold text-foreground">{event.title}</div>
                <p className="text-xs text-muted-foreground">{event.description}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-muted-foreground">
              <span>{shortDate(event.timestamp)}</span>
              <div className="flex items-center gap-2">
                <Badge className={`border text-[10px] ${token.color}`}>{token.label}</Badge>
                {event.link ? (
                  <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" asChild>
                    <a href={event.link} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const contextSourceLabels: Record<ContextSnippet["source"], string> = {
  docs: "Docs",
  slack: "Slack",
  ticket: "Tickets",
  support: "Support",
  cerebros: "Cerebros",
};

const sourceIconMap: Record<SignalSource, React.ComponentType<{ className?: string }>> = {
  git: GitCommit,
  docs: FileText,
  slack: MessageSquare,
  tickets: Ticket,
  support: LifeBuoy,
};

const ActivityStat = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-2xl border border-border/60 p-4">
    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="text-sm font-semibold text-foreground">{value}</div>
  </div>
);

const ComponentLiveIssueRow = ({
  projectId,
  component,
  issue,
  onOpen,
}: {
  projectId: string;
  component: ComponentNode;
  issue: DocIssue;
  onOpen: () => void;
}) => {
  const eventLinks =
    component.sourceEvents
      .filter((event) => issue.divergenceSources.includes(event.source) && event.link)
      .reduce<Record<string, SourceEvent>>((acc, event) => {
        if (event.link && !acc[event.source]) {
          acc[event.source] = event;
        }
        return acc;
      }, {}) ?? undefined;

  return (
    <div className="rounded-2xl border border-border/50 bg-background/80 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{issue.title}</div>
          <p className="text-xs text-muted-foreground line-clamp-2">{issue.summary}</p>
          <p className="text-[11px] text-muted-foreground">{describeIssueSignals(issue)}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase">
            {issue.severity}
          </Badge>
          <Button variant="ghost" size="sm" className="rounded-full" onClick={onOpen}>
            Inspect
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 pt-2 text-xs text-muted-foreground">
        <span>Sources • {issue.divergenceSources.join(", ")}</span>
        <span>Updated • {shortDate(issue.updatedAt)}</span>
        <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" asChild>
          <a href={`/projects/${projectId}/issues/${issue.id}`}>Open issue view</a>
        </Button>
      </div>
      {eventLinks ? (
        <div className="flex flex-wrap gap-2 pt-2 text-xs">
          {Object.values(eventLinks).map((event) => {
            const token = signalSourceTokens[event.source];
            return (
              <Badge key={event.id} variant="outline" className={`border text-[10px] ${token.color}`}>
                <a href={event.link} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                  View {token.label}
                </a>
              </Badge>
            );
          })}
        </div>
      ) : null}
    </div>
  );
};


