"use client";

import { formatDistanceToNow } from "date-fns";

import { LiveRecency } from "@/components/live/live-recency";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { Project } from "@/lib/types";

type WorkspaceCardProps = {
  project: Project;
};

export function SetupWorkspaceCard({ project }: WorkspaceCardProps) {
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const liveSnapshot = useDashboardStore((state) => state.liveSnapshot);

  const repoCount = project.repos.length;
  const slackChannels = collectSlackChannels(project);
  const gitConnected = repoCount > 0;
  const slackConnected = slackChannels.length > 0;
  const impactEnabled = Boolean(project.docIssues.length || project.changeImpacts.length);

  const activityLastRun = liveSnapshot?.generatedAt ?? liveStatus.lastUpdated ?? null;
  const latestDocIssue = project.docIssues.reduce<string | null>((acc, issue) => {
    if (!issue.updatedAt) return acc;
    if (!acc) return issue.updatedAt;
    return new Date(issue.updatedAt) > new Date(acc) ? issue.updatedAt : acc;
  }, null);

  const impactLastRun = latestDocIssue ?? liveStatus.lastUpdated ?? null;

  return (
    <Card className="border-border/70 bg-card/80">
      <CardHeader>
        <CardTitle>Workspace wiring</CardTitle>
        <CardDescription>Are the core integrations awake?</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 text-sm">
        <section>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Connections</p>
          <div className="mt-2 space-y-2">
            <ConnectionLine
              label="Git"
              value={
                gitConnected ? (
                  <>
                    Connected <Badge variant="outline" className="ml-2 rounded-full px-2 text-[11px]">{repoCount} repos</Badge>
                  </>
                ) : (
                  "Not connected"
                )
              }
            />
            <ConnectionLine
              label="Slack"
              value={
                slackConnected ? (
                  <>
                    Connected{" "}
                    <Badge variant="outline" className="ml-2 rounded-full px-2 text-[11px]">
                      {slackChannels.length} channels
                    </Badge>
                  </>
                ) : (
                  "Not connected"
                )
              }
            />
          </div>
        </section>

        <section>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</p>
          <div className="mt-2 space-y-2 text-sm">
            <StatusLine label="Activity graph ingest" value={formatRelative(activityLastRun)} />
            <StatusLine
              label="Impact analysis"
              value={
                impactEnabled
                  ? `Enabled — last issue update ${formatRelative(impactLastRun)}`
                  : "Disabled (no impact telemetry yet)"
              }
            />
            <LiveRecency className="!block text-[12px]" prefix="Live snapshot" />
          </div>
        </section>
      </CardContent>
    </Card>
  );
}

function collectSlackChannels(project: Project) {
  const channels = new Set<string>();
  project.repos.forEach((repo) => {
    repo.linkedSystems.slackChannels?.forEach((channel) => channels.add(channel));
  });
  return Array.from(channels);
}

function formatRelative(iso?: string | null) {
  if (!iso) return "no runs yet";
  try {
    return `${formatDistanceToNow(new Date(iso), { addSuffix: true })}`;
  } catch {
    return "timestamp unavailable";
  }
}

function ConnectionLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col rounded-2xl border border-border/50 px-3 py-2 text-[13px]">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}


