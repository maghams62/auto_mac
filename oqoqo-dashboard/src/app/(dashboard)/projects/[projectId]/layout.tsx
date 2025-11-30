"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";

import { useDashboardStore } from "@/lib/state/dashboard-store";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ projectId: string }>();
  const selectProject = useDashboardStore((state) => state.selectProject);
  const selectComponent = useDashboardStore((state) => state.selectComponent);
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;

  useEffect(() => {
    if (projectId) {
      selectProject(projectId);
      selectComponent(undefined);
    }
  }, [projectId, selectProject, selectComponent]);

  return <>{children}</>;
}

