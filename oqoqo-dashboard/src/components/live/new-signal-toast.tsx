"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";

export function NewSignalToast({ projectId }: { projectId: string }) {
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const prevIssueIds = useRef<Set<string>>(new Set());
  const [visibleMessage, setVisibleMessage] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!project) return;
    const liveIssues = project.docIssues.filter((issue) => issue.id.startsWith("live_issue"));
    const currentIds = new Set(liveIssues.map((issue) => issue.id));
    const prevIds = prevIssueIds.current;

    if (prevIds.size) {
      const newIssues = liveIssues.filter((issue) => !prevIds.has(issue.id));
      if (newIssues.length) {
        const message =
          newIssues.length === 1
            ? `New live issue detected (${newIssues[0].severity})`
            : `${newIssues.length} new live issues detected`;
        const frame = requestAnimationFrame(() => setVisibleMessage(message));
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => setVisibleMessage(null), 4000);
        prevIssueIds.current = currentIds;
        return () => {
          cancelAnimationFrame(frame);
        };
      }
    }

    prevIssueIds.current = currentIds;
  }, [project?.docIssues, liveStatus.lastUpdated, project]);

  if (!visibleMessage) {
    return null;
  }

  return (
    <Badge variant="outline" className="flex items-center gap-1 rounded-full border-amber-300/60 bg-amber-500/10 text-xs text-amber-100">
      <Sparkles className="h-3 w-3" />
      {visibleMessage}
    </Badge>
  );
}

