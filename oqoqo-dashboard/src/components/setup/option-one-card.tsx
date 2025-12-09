"use client";

import { useEffect, useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { MessageSquare } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LinkChip } from "@/components/common/link-chip";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { ActivitySummary } from "@/lib/api/activity";
import { fetchTopComponents, isCerebrosApiConfigured } from "@/lib/api/activity";
import type { Project, SlackThread } from "@/lib/types";

type OptionOneCardProps = {
  project: Project;
};

export function SetupOptionOneCard({ project }: OptionOneCardProps) {
  const [rows, setRows] = useState<ActivitySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const liveSnapshot = useDashboardStore((state) => state.liveSnapshot);

  const fallbackRows = useMemo(() => buildFallbackActivity(project), [project]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!isCerebrosApiConfigured()) {
        setRows(fallbackRows);
        setError(null);
        return;
      }

      setLoading(true);
      try {
        const data = await fetchTopComponents({ limit: 5 });
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load activity graph data");
          setRows(fallbackRows);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [fallbackRows]);

  const summarySentence = buildSummarySentence(project);
  const activityList = rows.slice(0, 3).map((row) => resolveComponentName(project, row.componentId));
  const mostActive =
    activityList.length > 0
      ? `Most active components (24h): ${activityList.join(", ")}`
      : "No components surfaced in the last day.";

  const incidentThread = pickIncidentThread(liveSnapshot?.slack ?? []);
  const channelSummary = incidentThread
    ? summarizeSlackThread(incidentThread)
    : buildEmptySlackSummary();

  return (
    <Card className="border-border/70 bg-card/80">
      <CardHeader>
        <CardTitle>Option 1 · Activity Graph</CardTitle>
        <CardDescription>{summarySentence}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {loading ? <p className="text-muted-foreground">Fetching latest telemetry…</p> : null}
        {error ? <p className="text-amber-200">{error}</p> : null}
        <ul className="space-y-2">
          <li>{mostActive}</li>
          <li>{channelSummary.headline}</li>
        </ul>
        {incidentThread ? (
          <div className="rounded-2xl border border-border/60 p-3">
            <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
              <MessageSquare className="h-4 w-4 text-primary" />
              Last message · {incidentThread.channel}
            </div>
            <p className="mt-2 text-sm text-foreground">{channelSummary.detail}</p>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>{formatDistanceToNow(new Date(incidentThread.lastActivityTs), { addSuffix: true })}</span>
              {incidentThread.user ? <span>by {incidentThread.user}</span> : null}
              <LinkChip
                label="Open in Slack"
                href={incidentThread.permalink}
                variant="ghost"
                size="sm"
                className="h-auto px-0 text-xs text-primary underline-offset-4 hover:text-primary/80 hover:underline"
              />
            </div>
          </div>
        ) : null}
        {activityList.length ? (
          <div className="flex flex-wrap gap-2 text-xs">
            {rows.slice(0, 5).map((row) => (
              <Badge key={row.componentId} variant="outline" className="rounded-full border-border/50">
                {resolveComponentName(project, row.componentId)} · {row.activityScore.toFixed(1)}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function buildSummarySentence(project: Project) {
  const repoCount = project.repos.length;
  const componentCount = project.components.length;
  const slackChannels = collectSlackChannels(project);
  return `Activity graph is live for ${componentCount} components across ${repoCount} repos and ${slackChannels.length} Slack channels.`;
}

function buildFallbackActivity(project: Project): ActivitySummary[] {
  return project.components
    .map((component) => {
      const gitEvents = component.sourceEvents.filter((event) => event.source === "git").length;
      const slackEvents = component.sourceEvents.filter((event) => event.source === "slack").length;
      return {
        componentId: component.id,
        activityScore: component.graphSignals.activity.score,
        gitEvents,
        slackEvents,
        docDriftEvents: component.divergenceInsights.length,
        lastEventAt: component.graphSignals.timeline.at(-1)?.timestamp,
      } satisfies ActivitySummary;
    })
    .sort((a, b) => b.activityScore - a.activityScore);
}

function resolveComponentName(project: Project, componentId: string) {
  return project.components.find((component) => component.id === componentId)?.name ?? componentId;
}

function pickIncidentThread(threads: SlackThread[]) {
  if (!threads.length) return null;
  const incident = threads.find((thread) => thread.channel.toLowerCase().includes("incident"));
  return incident ?? threads[0];
}

type SlackSummary = { headline: string; detail: string };

function summarizeSlackThread(thread: SlackThread): SlackSummary {
  const clean = collapseWhitespace(thread.text);
  return {
    headline: clean || `Activity in ${thread.channel}`,
    detail: clean,
  };
}

function buildEmptySlackSummary(): SlackSummary {
  return {
    headline: "No incident-related chatter captured in the monitored channels.",
    detail: "No new Slack conversations were detected for the monitored components.",
  };
}

function collapseWhitespace(text: string | undefined) {
  if (!text) return "";
  const trimmed = text.replace(/\s+/g, " ").trim();
  return trimmed.length > 180 ? `${trimmed.slice(0, 177)}…` : trimmed;
}

function collectSlackChannels(project: Project) {
  const channels = new Set<string>();
  project.repos.forEach((repo) => {
    repo.linkedSystems.slackChannels?.forEach((channel) => channels.add(channel));
  });
  return Array.from(channels);
}


