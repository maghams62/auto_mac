import { ProjectRouteHydrator } from "@/components/layout/project-route-hydrator";

type ProjectParams = {
  projectId: string | string[];
};

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<ProjectParams> | ProjectParams;
}) {
  const resolvedParams = "then" in params ? await params : params;
  const projectId = Array.isArray(resolvedParams.projectId)
    ? resolvedParams.projectId[0]
    : resolvedParams.projectId;

  return <ProjectRouteHydrator projectId={projectId}>{children}</ProjectRouteHydrator>;
}

