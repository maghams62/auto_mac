"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  GitBranch,
  LayoutDashboard,
  Menu,
  Network,
  Search,
  Settings2,
  Shield,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ProjectSwitcher } from "@/components/layout/project-switcher";
import { HydrationDiagnostics } from "@/components/system/hydration-diagnostics";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { logClientEvent } from "@/lib/logging";
import { fetchApiEnvelope } from "@/lib/http/api-response";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import { describeMode, isLiveLike } from "@/lib/mode";
import { cn, shortTime } from "@/lib/utils";
import type { IngestStatusPayload, LiveActivitySnapshot, LiveMode, Project } from "@/lib/types";
import { workspaceNavItems } from "@/components/layout/nav-data";

const projectNavSections = [
  {
    heading: "Projects (Today)",
    items: [
      {
        label: "Today",
        description: "Doc health pulse, top issues, recent signals.",
        icon: Shield,
        getHref: (projectId: string) => `/projects/${projectId}`,
      },
      {
        label: "Issues inbox",
        description: "Focused DocIssue list across all signals.",
        icon: AlertTriangle,
        getHref: (projectId: string) => `/projects/${projectId}/issues`,
      },
      {
        label: "Investigations",
        description: "Trace Cerebros answers with linked evidence.",
        icon: Search,
        getHref: (projectId: string) => `/projects/${projectId}/investigations`,
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
  const modePreference = useDashboardStore((state) => state.modePreference);

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
    const isExternal = /^https?:\/\//i.test(href);
    const isActive = !isExternal && (pathname === href || pathname.startsWith(`${href}/`));
    const shouldAppendMode = href.includes("/investigations");
    const modeAwareHref =
      !isExternal && shouldAppendMode && modePreference
        ? `${href}${href.includes("?") ? "&" : "?"}mode=${modePreference}`
        : href;

    const linkClasses = cn(
      "group relative flex flex-col rounded-2xl border px-4 py-3 transition-all",
      isActive
        ? "border-primary/40 bg-primary/10 text-primary"
        : "border-transparent bg-transparent text-muted-foreground hover:border-border/60 hover:bg-muted/10 hover:text-foreground"
    );

    const content = (
      <>
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Icon className="h-4 w-4" />
          {label}
          <ArrowUpRight className="ml-auto h-3.5 w-3.5 opacity-0 transition group-hover:opacity-80" />
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </>
    );

    if (isExternal) {
      return (
        <a
          key={href + label}
          href={href}
          target="_blank"
          rel="noreferrer"
          className={linkClasses}
          onClick={() => logClientEvent("nav.click", { href, label })}
        >
          {content}
        </a>
      );
    }

    return (
      <Link
        key={href + label}
        href={modeAwareHref}
        onClick={() => logClientEvent("nav.click", { href, label })}
        className={linkClasses}
      >
        {content}
      </Link>
    );
  };

  const sidebarContent = (
    <SidebarNav
      baseNav={workspaceNavItems}
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
              <div className="text-[11px] font-semibold uppercase tracking-[0.5em] text-muted-foreground">OQOQO</div>
              <div className="text-xl md:text-2xl font-semibold tracking-tight text-foreground">
                Activity Graph Intelligence
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <IngestStatusWidget />
            <Button asChild variant="outline" className="rounded-full border-border/60 text-xs md:text-sm font-semibold">
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
  const modePreference = useDashboardStore((state) => state.modePreference);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const params = new URLSearchParams();
        if (modePreference) {
          params.set("mode", modePreference);
        }
        const payload = await fetchApiEnvelope<{ snapshot?: LiveActivitySnapshot; projects?: Project[] }>(
          `/api/activity${params.size ? `?${params.toString()}` : ""}`,
          {
            cache: "no-store",
          },
        );
        const data = payload.data;
        if (!cancelled && data?.snapshot && Array.isArray(data.projects)) {
          applyLiveProjects(data.projects as Project[], data.snapshot as LiveActivitySnapshot, payload.mode);
          const message = describeLiveStatus(payload.status, payload.fallbackReason, payload.error?.message);
          if (message) {
            setLiveStatus({
              mode: payload.mode ?? useDashboardStore.getState().liveStatus.mode,
              lastUpdated: data.snapshot.generatedAt,
              message,
            });
          }
        } else if (!cancelled) {
          const lastUpdated = useDashboardStore.getState().liveStatus.lastUpdated;
          setLiveStatus({
            mode: "error",
            lastUpdated,
            message: payload.error?.message ?? "Live payload missing data",
          });
        }
      } catch (error) {
        if (!cancelled) {
          console.error("[AppShell] Failed to load live activity", error);
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
  }, [applyLiveProjects, setLiveStatus, modePreference]);

  return null;
}

function ModeToggle() {
  const modePreference = useDashboardStore((state) => state.modePreference);
  const setModePreference = useDashboardStore((state) => state.setModePreference);

  return (
    <Tabs
      value={modePreference === "synthetic" ? "synthetic" : "atlas"}
      onValueChange={(next) => setModePreference(next === "synthetic" ? "synthetic" : "atlas")}
      className="min-w-[220px]"
      data-testid="mode-toggle"
    >
      <TabsList className="grid h-auto grid-cols-2 rounded-full border border-border/60 bg-background/80 p-1 text-xs">
        <TabsTrigger value="atlas" className="rounded-full px-3 py-1 text-[11px]">
          Live data
        </TabsTrigger>
        <TabsTrigger value="synthetic" className="rounded-full px-3 py-1 text-[11px]">
          Synthetic demo
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}

function SidebarNav({
  baseNav: baseNavItems,
  projectNavSections: projectSections,
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
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">OQOQO</div>
        <div className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">OQOQO Drift Dashboard</div>
        <p className="text-sm text-muted-foreground">DocDrift-inspired cockpit with activity graph context.</p>
      </div>

      <ContextSwitcher />

      <nav className="space-y-4">
        <NavSection heading="Workspace">
          {baseNavItems.map((item) => renderNavLink(item.href, item.label, item.description, item.icon))}
        </NavSection>
        {projectSections.map((section) => (
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
    <div className="mt-auto rounded-2xl border border-border/60 bg-muted/10 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Doc health</div>
      <div className="flex items-center justify-between pt-2">
        <div>
          <p className="text-sm font-semibold text-foreground">{project.name}</p>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{project.horizon}</p>
        </div>
        <div className="text-3xl font-bold text-primary">{project.docHealthScore}</div>
      </div>
      {project.pulse?.lastRefreshed ? (
        <p className="text-[11px] text-muted-foreground/90">Updated {shortTime(project.pulse.lastRefreshed)}</p>
      ) : null}
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
    isLiveLike(liveStatus.mode)
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

function IngestStatusWidget() {
  const [statusPayload, setStatusPayload] = useState<IngestStatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const envelope = await fetchApiEnvelope<IngestStatusPayload>("/api/ingest-status", {
          cache: "no-store",
        });
        if (cancelled) return;
        if (envelope.status === "OK" && envelope.data) {
          setStatusPayload(envelope.data);
          setError(null);
        } else {
          setStatusPayload(envelope.data ?? null);
          setError(envelope.error?.message ?? "Ingest status unavailable");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load ingest status");
        }
      }
    };
    load();
    const interval = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!statusPayload && !error) {
    return null;
  }

  const sources = statusPayload?.sources;
  const entries = [
    {
      key: "slack",
      label: "Slack",
      data: sources?.slack,
      detailKey: sources?.slack?.lastIngestAt ?? sources?.slack?.channels?.[0]?.lastMessageAt ?? null,
    },
    {
      key: "git",
      label: "Git",
      data: sources?.git,
      detailKey: sources?.git?.lastCommitAt ?? sources?.git?.lastPullRequestAt ?? sources?.git?.lastIssueAt ?? null,
    },
    {
      key: "doc",
      label: "Doc issues",
      data: sources?.doc_issues,
      detailKey: sources?.doc_issues?.lastRunAt ?? sources?.doc_issues?.docIssuesFileUpdatedAt ?? null,
    },
  ].filter((entry) => entry.data);

  const renderBadge = (label: string, sourceMode: string | undefined, status?: string, detail?: string | null) => {
    const tone =
      status === "ok"
        ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10"
        : status === "stale"
        ? "text-amber-200 border-amber-400/40 bg-amber-500/10"
        : status === "idle"
        ? "text-muted-foreground border-border/60"
        : "text-muted-foreground/70 border-border/40";
    const indicatorClass =
      status === "ok"
        ? "bg-emerald-300"
        : status === "stale"
        ? "bg-amber-300"
        : status === "idle"
        ? "bg-muted-foreground/60"
        : "bg-muted-foreground/30";
    const modeLabel = sourceMode === "live" ? "Live" : "Synthetic";
    const detailText = detail ? `Updated ${shortTime(detail)}` : "No recent data";
    return (
      <div key={label} className={cn("flex items-center gap-2 rounded-full border px-3 py-1 text-[11px]", tone)}>
        <span className={`h-2 w-2 rounded-full ${indicatorClass}`} aria-hidden="true" />
        <span className="font-semibold">{label}</span>
        <span className="text-muted-foreground/60">•</span>
        <span>{modeLabel}</span>
        <span className="text-muted-foreground/60">•</span>
        <span>{detailText}</span>
      </div>
    );
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {entries.map((entry) => renderBadge(entry.label, entry.data?.mode, entry.data?.status, entry.detailKey))}
      {error ? (
        <div className="rounded-full border border-amber-400/40 bg-amber-500/10 px-3 py-1 text-[11px] text-amber-200">
          Ingest status: {error}
        </div>
      ) : null}
    </div>
  );
}

function describeLiveStatus(status: string, fallbackReason?: string, errorMessage?: string) {
  if (status === "OK") {
    return undefined;
  }
  if (fallbackReason === "cerebros_unavailable") {
    return "Cerebros unavailable, showing ingest fallback";
  }
  if (fallbackReason === "synthetic_fallback") {
    return "Synthetic fixtures in use";
  }
  return errorMessage ?? "Live ingest degraded";
}

