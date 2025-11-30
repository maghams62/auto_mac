"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, AlertTriangle, ArrowUpRight, GitBranch, LayoutDashboard, Menu, Network, Settings2, Shield } from "lucide-react";
import { useEffect, useState } from "react";

import { ProjectSwitcher } from "@/components/layout/project-switcher";
import { HydrationDiagnostics } from "@/components/system/hydration-diagnostics";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { logClientEvent } from "@/lib/logging";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import { describeMode, isLiveLike } from "@/lib/mode";
import { cn, shortTime } from "@/lib/utils";
import type { LiveActivitySnapshot, LiveMode, Project } from "@/lib/types";

const baseNav = [
  {
    label: "Projects & Sources",
    description: "Configure monitored repos and linked systems.",
    href: "/projects",
    icon: LayoutDashboard,
  },
];

const projectNavSections = [
  {
    heading: "Live status",
    items: [
      {
        label: "Doc Drift Overview",
        description: "Severity trends and prioritized drift issues.",
        icon: Shield,
        getHref: (projectId: string) => `/projects/${projectId}`,
      },
      {
        label: "Live Drift Inbox",
        description: "Focused DocIssue list across all signals.",
        icon: AlertTriangle,
        getHref: (projectId: string) => `/projects/${projectId}/issues`,
      },
    ],
  },
  {
    heading: "Systems & impact",
    items: [
      {
        label: "Component Explorer",
        description: "Signals per component across code, tickets, and chat.",
        icon: LayoutDashboard,
        getHref: (projectId: string) => `/projects/${projectId}/components`,
      },
      {
        label: "Activity Graph",
        description: "Visualize live nodes and dependencies.",
        icon: Network,
        getHref: (projectId: string) => `/projects/${projectId}/graph`,
      },
      {
        label: "Activity Monitor",
        description: "Cerebros-ranked components by drift risk.",
        icon: Activity,
        getHref: (projectId: string) => `/projects/${projectId}/activity`,
      },
      {
        label: "Cross-System Impact",
        description: "Dependencies and downstream documentation exposure.",
        icon: GitBranch,
        getHref: (projectId: string) => `/projects/${projectId}/impact`,
      },
    ],
  },
  {
    heading: "Configuration & ops",
    items: [
      {
        label: "Sources & Configuration",
        description: "Repo/branch matrix and exportable config.",
        icon: Settings2,
        getHref: (projectId: string) => `/projects/${projectId}/configuration`,
      },
      {
        label: "Operator Diagnostics",
        description: "Live ingest inspector and dataset health.",
        icon: Activity,
        getHref: (projectId: string) => `/projects/${projectId}/configuration#live-inspector`,
      },
    ],
  },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const selectedProjectId = useDashboardStore((state) => state.selectedProjectId);
  const projects = useDashboardStore((state) => state.projects);
  const selectedProject = projects.find((project) => project.id === selectedProjectId);
  const liveStatus = useDashboardStore((state) => state.liveStatus);

  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    logClientEvent("live-status", {
      mode: liveStatus.mode,
      lastUpdated: liveStatus.lastUpdated,
      message: liveStatus.message,
    });
  }, [liveStatus.mode, liveStatus.lastUpdated, liveStatus.message]);

  const renderNavLink = (
    href: string,
    label: string,
    description: string,
    Icon: React.ComponentType<{ className?: string }>
  ) => {
    const isActive = pathname === href || pathname.startsWith(`${href}/`);

    return (
      <Link
        key={href + label}
        href={href}
        onClick={() => logClientEvent("nav.click", { href, label })}
        className={cn(
          "group relative flex flex-col rounded-2xl border px-4 py-3 transition-all",
          isActive
            ? "border-primary/40 bg-primary/10 text-primary"
            : "border-transparent bg-transparent text-muted-foreground hover:border-border/60 hover:bg-muted/10 hover:text-foreground"
        )}
      >
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Icon className="h-4 w-4" />
          {label}
          <ArrowUpRight className="ml-auto h-3.5 w-3.5 opacity-0 transition group-hover:opacity-80" />
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </Link>
    );
  };

  const sidebarContent = (
    <SidebarNav
      baseNav={baseNav}
      projectNavSections={projectNavSections}
      selectedProjectId={selectedProjectId}
      selectedProject={selectedProject}
      renderNavLink={renderNavLink}
    />
  );

  return (
    <div className="flex min-h-screen bg-grid-fade/[0.4]">
      <HydrationDiagnostics />
      <LiveActivityLoader />
      <div className="hidden w-[320px] lg:block">{sidebarContent}</div>

      <div className="flex flex-1 flex-col">
        <header className="flex flex-col gap-3 border-b border-border/60 bg-background/70 px-4 py-4 backdrop-blur lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <SheetTrigger asChild className="lg:hidden">
                <Button variant="outline" size="icon" className="rounded-xl border-border/60">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-[300px] border-border/60 bg-background/90 px-0">
                {sidebarContent}
              </SheetContent>
            </Sheet>
            <div className="hidden lg:block">
              <div className="text-xs uppercase tracking-[0.5em] text-muted-foreground">Oqoqo</div>
              <div className="text-lg font-semibold">Activity Graph Intelligence</div>
              {selectedProject ? (
                <p className="text-xs text-muted-foreground">
                  Focused on <span className="text-foreground">{selectedProject.name}</span>{" "}
                  <Badge variant="outline" className="ml-1 rounded-full border-primary/30 text-[10px] text-primary">
                    {selectedProject.horizon}
                  </Badge>
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Select a project from the sidebar to get started.</p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <LiveStatusWidget />
            <Button asChild variant="outline" className="rounded-full border-border/60 text-sm font-semibold">
              <Link href="/projects">Configure sources</Link>
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-background/95 px-4 py-6 lg:px-8">
          {liveStatus.mode === "error" && liveStatus.message ? (
            <div className="mb-4 rounded-2xl border border-amber-400/60 bg-amber-500/10 p-3 text-sm text-amber-200">
              Live ingest unavailable: {liveStatus.message}. Showing last known snapshot or mock data.
            </div>
          ) : null}
          {children}
        </main>
      </div>
    </div>
  );
}

function LiveActivityLoader() {
  const applyLiveProjects = useDashboardStore((state) => state.applyLiveProjects);
  const setLiveStatus = useDashboardStore((state) => state.setLiveStatus);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch("/api/activity");
        if (!response.ok) {
          let message = response.statusText;
          try {
            const payload = await response.json();
            if (payload?.error) {
              message = payload.error;
            }
          } catch {
            // ignore
          }
          if (!cancelled) {
            const lastUpdated = useDashboardStore.getState().liveStatus.lastUpdated;
            setLiveStatus({
              mode: "error",
              lastUpdated,
              message: message || "Unable to load live data",
            });
          }
          return;
        }
        const payload = (await response.json()) as {
          snapshot?: LiveActivitySnapshot;
          projects?: Project[];
          mode?: LiveMode;
        };
        if (!cancelled && payload.snapshot && Array.isArray(payload.projects)) {
          applyLiveProjects(payload.projects, payload.snapshot, payload.mode);
        } else if (!cancelled) {
          const lastUpdated = useDashboardStore.getState().liveStatus.lastUpdated;
          setLiveStatus({
            mode: "error",
            lastUpdated,
            message: "Live payload missing data",
          });
        }
      } catch (error) {
        if (!cancelled) {
          console.warn("Failed to load live activity", error);
          const lastUpdated = useDashboardStore.getState().liveStatus.lastUpdated;
          setLiveStatus({
            mode: "error",
            lastUpdated,
            message: "Failed to reach live activity endpoint",
          });
        }
      }
    };

    load();
    const interval = setInterval(load, 60_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [applyLiveProjects, setLiveStatus]);

  return null;
}

function SidebarNav({
  baseNav,
  projectNavSections,
  selectedProjectId,
  selectedProject,
  renderNavLink,
}: {
  baseNav: typeof baseNav;
  projectNavSections: typeof projectNavSections;
  selectedProjectId?: string;
  selectedProject?: Project;
  renderNavLink: (
    href: string,
    label: string,
    description: string,
    Icon: React.ComponentType<{ className?: string }>
  ) => React.ReactNode;
}) {
  return (
    <aside className="flex h-full flex-col gap-6 border-r border-border/60 bg-background/80 px-6 py-8">
      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">Oqoqo</div>
        <div className="text-2xl font-semibold text-foreground">Drift Dashboard</div>
        <p className="text-sm text-muted-foreground">DocDrift-inspired cockpit with activity graph context.</p>
      </div>

      <ContextSwitcher />

      <nav className="space-y-4">
        <NavSection heading="Workspace">
          {baseNav.map((item) => renderNavLink(item.href, item.label, item.description, item.icon))}
        </NavSection>
        {projectNavSections.map((section) => (
          <NavSection key={section.heading} heading={section.heading}>
            {selectedProjectId
              ? section.items.map((item) =>
                  renderNavLink(item.getHref(selectedProjectId), item.label, item.description, item.icon)
                )
              : section.items.map((item) => (
                  <div
                    key={item.label}
                    className="flex flex-col gap-1 rounded-2xl border border-dashed border-border/40 px-4 py-3 text-sm text-muted-foreground/70"
                  >
                    <div className="flex items-center gap-2">
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </div>
                    <p className="text-xs">Select a project to enable.</p>
                  </div>
                ))}
          </NavSection>
        ))}
      </nav>

      {selectedProject ? <ProjectHealthCard project={selectedProject} /> : null}
    </aside>
  );
}

function NavSection({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{heading}</p>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

function ProjectHealthCard({ project }: { project: Project }) {
  return (
    <div className="mt-auto rounded-2xl border border-border/60 bg-muted/20 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Doc health</div>
      <div className="flex items-center gap-2 pt-2">
        <span className="text-3xl font-bold text-primary">{project.docHealthScore}</span>
        <span className="text-sm text-muted-foreground">/ 100</span>
      </div>
      <p className="text-xs text-muted-foreground">
        {project.docHealthScore > 80
          ? "Docs are healthy with low drift."
          : project.docHealthScore > 60
          ? "Drift increasing. Prioritize high-risk nodes."
          : "Docs are at risk. Escalate remediation."}
      </p>
    </div>
  );
}

function ContextSwitcher() {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/5 p-3">
      <ProjectSwitcher />
    </div>
  );
}

function LiveStatusWidget() {
  const liveStatus = useDashboardStore((state) => state.liveStatus);

  const tone =
    isLiveLike(liveStatus.mode)
      ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10"
      : liveStatus.mode === "error"
      ? "text-amber-200 border-amber-400/40 bg-amber-500/10"
      : "text-muted-foreground border-border/60";

  const indicatorClass =
    isLiveLike(liveStatus.mode) || liveStatus.mode === "atlas"
      ? "bg-emerald-300"
      : liveStatus.mode === "error"
      ? "bg-amber-300"
      : "bg-muted-foreground/50";

  const detail =
    isLiveLike(liveStatus.mode) && liveStatus.lastUpdated
      ? `Updated ${shortTime(liveStatus.lastUpdated)}`
      : liveStatus.mode === "error"
      ? liveStatus.message ?? "Live ingest unavailable"
      : liveStatus.mode === "hybrid"
      ? "Hybrid ingest mode"
      : liveStatus.mode === "synthetic"
      ? "Synthetic fixtures"
      : describeMode(liveStatus.mode);

  const modeLabel =
    liveStatus.mode === "atlas"
      ? "Atlas ingest"
      : liveStatus.mode === "hybrid"
      ? "Hybrid ingest"
      : liveStatus.mode === "error"
      ? "Ingest issue"
      : "Synthetic mode";

  return (
    <div className={cn("flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium", tone)}>
      <span className={`h-2 w-2 rounded-full ${indicatorClass}`} aria-hidden="true" />
      <span>{modeLabel}</span>
      <span className="text-muted-foreground/60">•</span>
      <span className="text-[11px]">{detail}</span>
    </div>
  );
}

