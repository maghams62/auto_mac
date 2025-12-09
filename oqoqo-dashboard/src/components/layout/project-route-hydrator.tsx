"use client";

import { useEffect } from "react";

import { useDashboardStore } from "@/lib/state/dashboard-store";

export function ProjectRouteHydrator({
  projectId,
  children,
}: {
  projectId?: string;
  children: React.ReactNode;
}) {
  const selectProject = useDashboardStore((state) => state.selectProject);
  const selectComponent = useDashboardStore((state) => state.selectComponent);

  useEffect(() => {
    if (projectId) {
      selectProject(projectId);
      selectComponent(undefined);
    }
  }, [projectId, selectProject, selectComponent]);

  return <>{children}</>;
}

