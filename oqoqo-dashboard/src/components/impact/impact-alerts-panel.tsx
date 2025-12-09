"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DeepLinkButtons } from "@/components/common/deep-link-buttons";
import { impactAlertsCopy, type ImpactAlert } from "@/lib/mock-impact-alerts";
import { fetchApiEnvelope } from "@/lib/http/api-response";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { LiveMode } from "@/lib/types";
import { severityTokens } from "@/lib/ui/tokens";
import { longDateTime } from "@/lib/utils";

type LoadState = "loading" | "ready" | "error";

export function ImpactAlertsPanel({ projectId }: { projectId?: string }) {
  const [alerts, setAlerts] = useState<ImpactAlert[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [impactLevelFilter, setImpactLevelFilter] = useState<string>("all");
  const [componentFilter, setComponentFilter] = useState<string>("");
  const [serviceFilter, setServiceFilter] = useState<string>("");
  const [modeMeta, setModeMeta] = useState<{ mode: LiveMode; fallback: boolean }>({
    mode: "synthetic",
    fallback: true,
  });
  const modePreference = useDashboardStore((dashboard) => dashboard.modePreference);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ source: "impact-report" });
    if (impactLevelFilter && impactLevelFilter !== "all") {
      params.set("impact_level", impactLevelFilter);
    }
    if (componentFilter.trim()) {
      params.set("component_id", componentFilter.trim());
    }
    if (serviceFilter.trim()) {
      params.set("service_id", serviceFilter.trim());
    }
    if (projectId) {
      params.set("project_id", projectId);
    }
    if (modePreference) {
      params.set("mode", modePreference);
    }
    return params.toString();
  }, [impactLevelFilter, componentFilter, serviceFilter, projectId, modePreference]);

  useEffect(() => {
    const controller = new AbortController();
    const loadAlerts = async () => {
      setState("loading");
      try {
        const payload = await fetchApiEnvelope<ImpactDocIssueResponse>(`/api/impact/doc-issues?${queryString}`, {
          signal: controller.signal,
          cache: "no-store",
        });
        const mapped = (payload.data?.doc_issues ?? []).map(mapDocIssueToAlert);
        if (!controller.signal.aborted) {
          setAlerts(mapped);
          setModeMeta({
            mode: payload.data?.mode ?? payload.mode ?? "synthetic",
            fallback: Boolean(payload.data?.fallback),
          });
          setStatusMessage(
            payload.status === "OK"
              ? null
              : describeDocIssuesStatus(payload.fallbackReason, payload.error?.message),
          );
          setState("ready");
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        console.error("[ImpactAlertsPanel] Failed to fetch doc issues", error);
        setState("error");
      }
    };
    loadAlerts();
    return () => controller.abort();
  }, [queryString]);

  return (
    <Card className="border border-border/70 bg-card/80" data-testid="impact-alerts-panel">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-3 text-lg font-semibold">
          {impactAlertsCopy.title}
          <Badge variant="outline" className="rounded-full border-border/40 text-[10px] uppercase">
            {describeMode(modeMeta)}
          </Badge>
        </CardTitle>
        <CardDescription>{statusMessage ?? impactAlertsCopy.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap gap-3 text-xs">
          <FilterBlock label="Impact level">
            <Select value={impactLevelFilter} onValueChange={setImpactLevelFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
          </FilterBlock>
          <FilterBlock label="Component ID">
            <Input
              value={componentFilter}
              onChange={(event) => setComponentFilter(event.target.value)}
              placeholder="comp:payments"
              className="w-40"
            />
          </FilterBlock>
          <FilterBlock label="Service ID">
            <Input
              value={serviceFilter}
              onChange={(event) => setServiceFilter(event.target.value)}
              placeholder="svc:payments"
              className="w-40"
            />
          </FilterBlock>
        </div>
        {state === "loading" ? (
          <LoadingState />
        ) : state === "error" ? (
          <div className="rounded-2xl border border-dashed border-destructive/40 p-4 text-sm text-destructive">
            {impactAlertsCopy.error}
          </div>
        ) : alerts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/50 p-4 text-sm text-muted-foreground">
            {impactAlertsCopy.empty}
          </div>
        ) : (
          <div className="space-y-4">
            {alerts.map((alert) => (
              <AlertRow key={alert.id} alert={alert} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const AlertRow = ({ alert }: { alert: ImpactAlert }) => {
  const severity = severityTokens[alert.impactLevel];
  return (
    <div className="space-y-3 rounded-2xl border border-border/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{alert.docName}</p>
          <p className="text-xs text-muted-foreground">{alert.repoPath}</p>
        </div>
        <Badge className={`border text-[10px] ${severity.color}`}>{severity.label}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">{alert.summary}</p>
      <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground">
        <span>{longDateTime(alert.timestamp)}</span>
        <span>Alert ID • {alert.id}</span>
      </div>
      <DeepLinkButtons githubUrl={alert.githubUrl} slackUrl={alert.slackUrl} docUrl={alert.docUrl} />
    </div>
  );
};

const LoadingState = () => (
  <div className="space-y-3">
    {Array.from({ length: 2 }).map((_, index) => (
      <div key={`loading-${index}`} className="space-y-3 rounded-2xl border border-border/40 p-4">
        <div className="flex items-center justify-between">
          <div className="h-3 w-40 animate-pulse rounded-full bg-muted/40" />
          <div className="h-4 w-16 animate-pulse rounded-full bg-muted/40" />
        </div>
        <div className="h-3 w-full animate-pulse rounded-full bg-muted/30" />
        <div className="h-3 w-2/3 animate-pulse rounded-full bg-muted/20" />
        <div className="flex gap-2">
          <div className="h-8 w-20 animate-pulse rounded-full bg-muted/30" />
          <div className="h-8 w-28 animate-pulse rounded-full bg-muted/30" />
        </div>
      </div>
    ))}
  </div>
);

type ImpactDocIssueResponse = {
  doc_issues?: DocIssue[];
  mode?: LiveMode;
  fallback?: boolean;
};

type DocIssueLink = {
  type?: string;
  url?: string;
};

type DocIssue = {
  id: string;
  doc_title?: string;
  doc_path?: string;
  doc_url?: string;
  github_url?: string;
  slack_url?: string;
  repo_id?: string;
  impact_level?: string;
  summary?: string;
  detected_at?: string;
  updated_at?: string;
  created_at?: string;
  links?: DocIssueLink[];
  change_context?: {
    url?: string;
    slack_permalink?: string;
  };
  slack_context?: {
    permalink?: string;
  };
};

const severityFallback = (level?: string): ImpactAlert["impactLevel"] => {
  const normalized = (level || "").toLowerCase();
  if (normalized === "high") {
    return "high";
  }
  if (normalized === "low") {
    return "low";
  }
  return "medium";
};

const getLink = (issue: DocIssue, linkType: string) =>
  issue.links?.find((link) => link.type === linkType)?.url;

const mapDocIssueToAlert = (issue: DocIssue): ImpactAlert => {
  const docName =
    issue.doc_title ||
    issue.doc_path?.split("/").pop() ||
    issue.doc_path ||
    issue.id;
  const repoPrefix = issue.repo_id || "";
  const path = issue.doc_path || "";
  const repoPath = [repoPrefix, path].filter(Boolean).join(path ? "/" : "");
  const githubUrl = issue.github_url || getLink(issue, "git") || issue.change_context?.url;
  const slackUrl =
    issue.slack_url ||
    getLink(issue, "slack") ||
    issue.change_context?.slack_permalink ||
    issue.slack_context?.permalink;
  const docUrl = issue.doc_url || getLink(issue, "doc");
  const timestamp = issue.updated_at || issue.detected_at || issue.created_at || new Date().toISOString();

  return {
    id: issue.id,
    docName,
    repoPath: repoPath || issue.doc_title || issue.id,
    impactLevel: severityFallback(issue.impact_level),
    summary: issue.summary || "Documentation flagged by recent impact analysis.",
    timestamp,
    githubUrl,
    slackUrl,
    docUrl,
  };
};

const describeMode = (meta: { mode: LiveMode; fallback: boolean }) => {
  if (meta.fallback) {
    return "Synthetic fallback";
  }
  if (meta.mode === "atlas" || meta.mode === "hybrid") {
    return "Live data";
  }
  if (meta.mode === "error") {
    return "Ingest error";
  }
  return "Synthetic data";
};

const FilterBlock = ({ label, children }: { label: string; children: ReactNode }) => (
  <div className="flex items-center gap-2">
    <span className="text-muted-foreground">{label}</span>
    {children}
  </div>
);

function describeDocIssuesStatus(fallbackReason?: string, errorMessage?: string) {
  if (!fallbackReason) {
    return errorMessage ?? null;
  }
  if (fallbackReason === "cerebros_unavailable") {
    return "Cerebros unavailable; showing fallback alerts.";
  }
  if (fallbackReason === "synthetic_fallback") {
    return "Synthetic fixtures in use.";
  }
  return errorMessage ?? null;
}

