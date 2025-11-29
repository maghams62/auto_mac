"use client";

import { useParams } from "next/navigation";

import { IssueDetailBody } from "@/components/issues/issue-detail";
import { Card } from "@/components/ui/card";
import { useDashboardStore } from "@/lib/state/dashboard-store";

export default function IssueDetailPage() {
  const params = useParams<{ projectId: string; issueId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const issueId = Array.isArray(params.issueId) ? params.issueId[0] : params.issueId;
  const projects = useDashboardStore((state) => state.projects);
  const project = projects.find((item) => item.id === projectId);
  const issue = project?.docIssues.find((item) => item.id === issueId);

  if (!project || !issue) {
    return <div className="text-sm text-destructive">Issue not found.</div>;
  }

  return (
    <Card className="max-w-5xl space-y-6 border-border/60 bg-card/80 p-6">
      <IssueDetailBody issue={issue} project={project} />
    </Card>
  );
}

