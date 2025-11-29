"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ArrowUpRight, GitBranch, LayoutDashboard, Menu, Settings2, Shield } from "lucide-react";
import { useState } from "react";

import { ProjectSwitcher } from "@/components/layout/project-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import { cn } from "@/lib/utils";

const baseNav = [
  {
    label: "Projects & Sources",
    description: "Configure monitored repos and linked systems.",
    href: "/projects",
    icon: LayoutDashboard,
  },
];

const projectNav = [
  {
    label: "Doc Drift Overview",
    description: "Severity trends and prioritized drift issues.",
    icon: Shield,
    getHref: (projectId: string) => `/projects/${projectId}`,
  },
  {
    label: "Activity Graph",
    description: "Signals per component across code, tickets, and chat.",
    icon: Activity,
    getHref: (projectId: string) => `/projects/${projectId}/components`,
  },
  {
    label: "Cross-System Impact",
    description: "Dependencies and downstream documentation exposure.",
    icon: GitBranch,
    getHref: (projectId: string) => `/projects/${projectId}/impact`,
  },
  {
    label: "Sources & Configuration",
    description: "Repo/branch matrix and exportable config.",
    icon: Settings2,
    getHref: (projectId: string) => `/projects/${projectId}/configuration`,
  },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const selectedProjectId = useDashboardStore((state) => state.selectedProjectId);
  const projects = useDashboardStore((state) => state.projects);
  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  const [mobileNavOpen, setMobileNavOpen] = useState(false);

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
    <aside className="flex h-full flex-col gap-6 border-r border-border/60 bg-background/80 px-6 py-8">
      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">Oqoqo</div>
        <div className="text-2xl font-semibold text-foreground">Drift Dashboard</div>
        <p className="text-sm text-muted-foreground">
          DocDrift-inspired cockpit with activity graph context.
        </p>
      </div>

      <ProjectSwitcher />

      <div className="space-y-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Workspace</span>
        {baseNav.map((item) => renderNavLink(item.href, item.label, item.description, item.icon))}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <span>Current project</span>
          {selectedProject ? (
            <Badge variant="outline" className="rounded-full border-primary/30 text-primary">
              {selectedProject.horizon}
            </Badge>
          ) : null}
        </div>
        <div className="flex flex-col gap-2">
          {projectNav.map((item) =>
            selectedProjectId ? (
              renderNavLink(item.getHref(selectedProjectId), item.label, item.description, item.icon)
            ) : (
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
            )
          )}
        </div>
      </div>

      {selectedProject ? (
        <div className="mt-auto rounded-2xl border border-border/60 bg-muted/20 p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Doc health</div>
          <div className="flex items-center gap-2 pt-2">
            <span className="text-3xl font-bold text-primary">{selectedProject.docHealthScore}</span>
            <span className="text-sm text-muted-foreground">/ 100</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {selectedProject.docHealthScore > 80
              ? "Docs are healthy with low drift."
              : selectedProject.docHealthScore > 60
              ? "Drift increasing. Prioritize high-risk nodes."
              : "Docs are at risk. Escalate remediation."}
          </p>
        </div>
      ) : null}
    </aside>
  );

  return (
    <div className="flex min-h-screen bg-grid-fade/[0.4]">
      <div className="hidden w-[320px] lg:block">{sidebarContent}</div>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border/60 bg-background/70 px-4 py-4 backdrop-blur lg:px-8">
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
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button asChild variant="outline" className="rounded-full border-border/60 text-sm font-semibold">
              <Link href="/projects">Configure sources</Link>
            </Button>
            <div className="hidden min-w-[220px] lg:block">
              <ProjectSwitcher compact />
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-background/95 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

