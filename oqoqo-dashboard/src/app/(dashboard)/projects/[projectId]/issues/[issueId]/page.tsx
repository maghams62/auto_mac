"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import { useParams } from "next/navigation";

import { AskOqoqoCard } from "@/components/common/ask-oqoqo";
import { ContextSourceBadge } from "@/components/context/context-source-badge";
import { IssueDetailBody } from "@/components/issues/issue-detail";
import { LiveRecency } from "@/components/live/live-recency";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { requestContextSnippets, sendContextFeedback } from "@/lib/context/client";
import type { ContextResponse, ContextSnippet } from "@/lib/context/types";
import { selectIssueById, selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { signalSourceTokens } from "@/lib/ui/tokens";
import type { SignalSource } from "@/lib/types";
import { longDateTime } from "@/lib/utils";

type TimelineEvent = {
  id: string;
  timestamp: string;
  source: SignalSource;
  title: string;
  description: string;
};

export default function IssueDetailPage() {
  const params = useParams<{ projectId: string; issueId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const issueId = Array.isArray(params.issueId) ? params.issueId[0] : params.issueId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const issueSelector = useMemo(() => selectIssueById(projectId, issueId), [projectId, issueId]);
  const project = useDashboardStore(projectSelector);
  const issue = useDashboardStore(issueSelector);

  const component = project?.components.find((item) => item.id === issue?.componentId);
  const repo = project?.repos.find((item) => item.id === issue?.repoId);
  const [contextOpen, setContextOpen] = useState(false);
  type ContextState = {
    data: ContextResponse | null;
    loading: boolean;
    error: string | null;
  };

  type ContextAction =
    | { type: "LOADING" }
    | { type: "SUCCESS"; data: ContextResponse }
    | { type: "ERROR"; error: string }
    | { type: "DISMISS"; snippetId: string };

  const contextReducer = (state: ContextState, action: ContextAction): ContextState => {
    switch (action.type) {
      case "LOADING":
        return { ...state, loading: true, error: null };
      case "SUCCESS":
        return { data: action.data, loading: false, error: null };
      case "ERROR":
        return { data: null, loading: false, error: action.error };
      case "DISMISS":
        if (!state.data) return state;
        return {
          ...state,
          data: {
            ...state.data,
            snippets: state.data.snippets.filter((snippet) => snippet.id !== action.snippetId),
          },
        };
      default:
        return state;
    }
  };

  const [contextState, dispatchContext] = useReducer(contextReducer, {
    data: null,
    loading: false,
    error: null,
  });

  const timelineEvents = useMemo<TimelineEvent[]>(() => {
    if (!project || !issue) return [];
    const events: TimelineEvent[] = [
      {
        id: `${issue.id}-detected`,
        timestamp: issue.detectedAt,
        source: issue.divergenceSources[0] ?? "docs",
        title: "Drift detected",
        description: issue.summary,
      },
      {
        id: `${issue.id}-updated`,
        timestamp: issue.updatedAt,
        source: issue.divergenceSources[1] ?? issue.divergenceSources[0] ?? "git",
        title: "Issue triaged",
        description: "Signals acknowledged and remediation planned.",
      },
    ];

    if (component?.sourceEvents.length) {
      component.sourceEvents
        .filter((event) => issue.divergenceSources.includes(event.source))
        .forEach((event) => {
          events.push({
            id: event.id,
            timestamp: event.timestamp,
            source: event.source,
            title: event.title,
            description: event.description,
          });
        });
    }

    return events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [component, issue, project]);

  useEffect(() => {
    if (!projectId || !issue?.id) {
      return;
    }
    let cancelled = false;
    dispatchContext({ type: "LOADING" });
    requestContextSnippets({ projectId, issueId: issue.id })
      .then((response) => {
        if (!cancelled) {
          dispatchContext({ type: "SUCCESS", data: response });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          dispatchContext({
            type: "ERROR",
            error: error instanceof Error ? error.message : "Failed to load context snippets",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, issue?.id]);

  if (!project || !issue) {
    return <div className="text-sm text-destructive">Issue not found.</div>;
  }

  const previewSnippets = contextState.data?.snippets.slice(0, 3) ?? [];
  const hasMoreContext = Boolean(
    contextState.data && contextState.data.snippets.length > previewSnippets.length
  );

  const handleDismissSnippet = async (snippetId: string) => {
    dispatchContext({ type: "DISMISS", snippetId });
    try {
      await sendContextFeedback({
        snippetId,
        dismissed: true,
        projectId,
        issueId: issue.id,
        componentId: issue.componentId,
      });
    } catch (error) {
      console.warn("Failed to send context feedback", error);
    }
  };

  const linkedArtifacts = [
    repo?.name
      ? {
          label: "Source of truth",
          value: repo.name,
          detail: repo.repoUrl,
        }
      : null,
    repo?.branch
      ? {
          label: "Branch",
          value: repo.branch,
        }
      : null,
    {
      label: "Doc path",
      value: issue.docPath,
    },
    ...issue.linkedCode.map((file) => ({
      label: "Linked file",
      value: file,
    })),
  ].filter(Boolean) as { label: string; value: string; detail?: string }[];

  return (
    <div className="space-y-6">
      <LiveRecency prefix="Timeline updated" />
      <div className="grid gap-6 lg:grid-cols-[1.3fr,1.3fr,1fr]">
        <Card className="border-border/60 bg-card/80">
          <CardContent className="p-6">
            <IssueDetailBody issue={issue} project={project} showAskCard={false} showDeepLinkButton={false} />
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle>Unified timeline</CardTitle>
            <CardDescription>How Git, docs, Slack, tickets, and support escalated this drift.</CardDescription>
          </CardHeader>
          <CardContent>
            {timelineEvents.length ? (
              <div className="relative space-y-6">
                {timelineEvents.map((event, index) => (
                  <TimelineItem key={event.id} event={event} isLast={index === timelineEvents.length - 1} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No timeline data available.</p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-border/60">
            <CardHeader>
              <CardTitle>Linked artifacts</CardTitle>
              <CardDescription>Docs, repos, and files tied to this drift.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {linkedArtifacts.map((artifact, index) => (
                <div key={`${artifact.label}-${artifact.value}-${index}`} className="rounded-2xl border border-border/40 p-3">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">{artifact.label}</div>
                  <div className="text-sm font-semibold text-foreground break-all">{artifact.value}</div>
                  {artifact.detail ? (
                    <a
                      href={artifact.detail}
                      className="text-xs text-primary underline-offset-2 hover:underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {artifact.detail}
                    </a>
                  ) : null}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Semantic context</CardTitle>
                <CardDescription>Docs, tickets, and chat threads referencing this issue.</CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-full text-xs"
                onClick={() => setContextOpen((open) => !open)}
              >
                {contextOpen ? "Hide" : "Show"}
              </Button>
            </CardHeader>
            {contextOpen ? (
              <CardContent className="space-y-4">
                {contextState.loading ? (
                  <p className="text-sm text-muted-foreground">Loading context…</p>
                ) : contextState.error ? (
                  <p className="text-sm text-muted-foreground">{contextState.error}</p>
                ) : previewSnippets.length ? (
                  <div className="space-y-3">
                    {previewSnippets.map((snippet) => (
                      <ContextSnippetItem key={snippet.id} snippet={snippet} onDismiss={handleDismissSnippet} />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No context snippets yet.</p>
                )}
                {hasMoreContext ? (
                  <p className="text-[11px] text-muted-foreground">
                    Additional snippets are available from the component context tab.
                  </p>
                ) : null}
                {contextState.data ? (
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <ContextSourceBadge response={contextState.data} />
                    <span>{contextState.data.snippets.length} total snippets</span>
                  </div>
                ) : null}
              </CardContent>
            ) : null}
          </Card>

          <AskOqoqoCard context="issue" title={issue.title} summary={issue.summary} />
        </div>
      </div>
    </div>
  );
}

const ContextSnippetItem = ({
  snippet,
  onDismiss,
}: {
  snippet: ContextSnippet;
  onDismiss: (snippetId: string) => void;
}) => {
  const token = signalSourceTokens[snippet.source];
  return (
    <div className="rounded-2xl border border-border/50 p-3">
      <div className="flex items-center justify-between gap-2">
        <Badge className={`border text-[10px] ${token.color}`}>{token.label}</Badge>
        <button
          type="button"
          onClick={() => onDismiss(snippet.id)}
          className="text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          Hide
        </button>
      </div>
      <p className="py-2 text-sm text-foreground">{snippet.summary}</p>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <a href={snippet.link} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">
          Open source
        </a>
        <span>{Math.round(snippet.confidence * 100)}% confident</span>
      </div>
    </div>
  );
};

const TimelineItem = ({ event, isLast }: { event: TimelineEvent; isLast: boolean }) => {
  const token = signalSourceTokens[event.source];
  return (
    <div className="relative pl-8">
      {!isLast && <span className="absolute left-3 top-4 h-full w-px bg-border/60" />}
      <span className="absolute left-2 top-3 h-3 w-3 rounded-full bg-primary" />
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {longDateTime(event.timestamp)}
        <Badge className={`border text-[10px] ${token.color}`}>{token.label}</Badge>
      </div>
      <div className="text-sm font-semibold text-foreground">{event.title}</div>
      <p className="text-xs text-muted-foreground">{event.description}</p>
    </div>
  );
};

