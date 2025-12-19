import Link from "next/link";

import { ModeBadge } from "@/components/common/mode-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buildInvestigationUrl } from "@/lib/cerebros";
import { Investigation } from "@/lib/types";
import { shortDate, shortTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

type PageParams = {
  projectId: string | string[];
};

type PageSearchParams = {
  componentId?: string;
  since?: string;
  mode?: string;
};

type InvestigationsResponse = {
  investigations: Investigation[];
  mode: "synthetic" | "atlas" | "hybrid" | "error";
};

export default async function ProjectInvestigationsPage({
  params,
  searchParams,
}: {
  params: Promise<PageParams> | PageParams;
  searchParams: Promise<PageSearchParams> | PageSearchParams;
}) {
  const resolvedParams = "then" in params ? await params : params;
  const resolvedSearch = "then" in searchParams ? await searchParams : searchParams;
  const projectId = Array.isArray(resolvedParams.projectId) ? resolvedParams.projectId[0] : resolvedParams.projectId;
  const componentFilter = resolvedSearch.componentId ?? "";
  const sinceFilter = resolvedSearch.since ?? "";

  const query = new URLSearchParams();
  if (projectId) {
    query.set("projectId", projectId);
  }
  if (componentFilter) {
    query.set("componentId", componentFilter);
  }
  if (sinceFilter) {
    query.set("since", sinceFilter);
  }
  query.set("limit", "25");
  if (resolvedSearch.mode) {
    query.set("mode", resolvedSearch.mode);
  }

  const origin = resolveDashboardOrigin();
  const response = await fetch(`${origin}/api/investigations?${query.toString()}`, {
    cache: "no-store",
  });
  let payload: InvestigationsResponse = { investigations: [], mode: "synthetic" };
  let error: string | null = null;
  if (!response.ok) {
    error = `Failed to load investigations (${response.status})`;
    try {
      const parsed = (await response.json()) as { error?: string };
      if (parsed?.error) {
        error = parsed.error;
      }
    } catch {
      // ignore parse failures
    }
  } else {
    payload = (await response.json()) as InvestigationsResponse;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">Traceability</p>
          <h1 className="text-2xl font-semibold text-foreground">Investigations</h1>
          <p className="text-sm text-muted-foreground">
            Every Cerebros answer that touched Slack/Git evidence now has a structured record. Filter by component or date to
            see what the team has been asking and jump straight to the source run.
          </p>
        </div>
        <div className="rounded-2xl border border-border/60 bg-muted/5 p-4">
          <form className="grid gap-4 md:grid-cols-3" method="get">
            {resolvedSearch.mode ? <input type="hidden" name="mode" value={resolvedSearch.mode} /> : null}
            <label className="flex flex-col gap-1 text-sm text-muted-foreground">
              Component filter
              <input
                className="rounded-xl border border-border/50 bg-background px-3 py-2 text-sm text-foreground"
                placeholder="component:atlas_core"
                name="componentId"
                defaultValue={componentFilter}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-muted-foreground">
              Since date
              <input
                className="rounded-xl border border-border/50 bg-background px-3 py-2 text-sm text-foreground"
                type="date"
                name="since"
                defaultValue={sinceFilter}
              />
            </label>
            <div className="flex items-end gap-2">
              <Button type="submit" className="flex-1 rounded-xl">
                Apply filters
              </Button>
              {(componentFilter || sinceFilter) && (
                <Button variant="outline" className="rounded-xl" asChild>
                  <Link href={`/projects/${projectId}/investigations`}>Reset</Link>
                </Button>
              )}
            </div>
          </form>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Mode</span>
            <ModeBadge mode={payload.mode} />
            <span>Showing up to 25 investigations.</span>
          </div>
        </div>
      </div>
      <InvestigationList investigations={payload.investigations} error={error} />
    </div>
  );
}

function resolveDashboardOrigin() {
  const envUrl =
    process.env.NEXT_PUBLIC_DASHBOARD_URL ??
    process.env.NEXT_PUBLIC_SITE_URL ??
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null);
  if (envUrl) {
    return envUrl.replace(/\/$/, "");
  }
  return "http://localhost:3000";
}

function InvestigationList({ investigations, error }: { investigations: Investigation[]; error?: string | null }) {
  if (error) {
    return (
      <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-6 text-sm text-amber-100">
        {error}
      </div>
    );
  }
  if (!investigations.length) {
    return (
      <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 p-6 text-center text-sm text-muted-foreground">
        No investigations yet. Ask Cerebros about this project via /slack or /git to seed the history.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {investigations.map((investigation) => {
        const investigationUrl = buildInvestigationUrl(investigation.id);
        return (
        <div
          key={investigation.id}
          className="rounded-2xl border border-border/60 bg-background/80 p-4 transition hover:border-primary/40"
        >
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              {shortDate(investigation.createdAt)} at {shortTime(investigation.createdAt)}
            </div>
            {investigation.status ? (
              <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase tracking-wide">
                {investigation.status}
              </Badge>
            ) : null}
            <div className="text-xs text-muted-foreground/80">Session {investigation.sessionId ?? "n/a"}</div>
            <div className="ml-auto flex items-center gap-2">
              {investigationUrl ? (
                <Button variant="outline" size="sm" className="rounded-full text-xs" asChild>
                  <Link href={investigationUrl} target="_blank">
                    Open in Cerebros
                  </Link>
                </Button>
              ) : (
                <p className="text-[11px] text-muted-foreground">Cerebros app URL not configured.</p>
              )}
            </div>
          </div>
          <h3 className="mt-2 text-lg font-semibold text-foreground">{investigation.question}</h3>
          {investigation.answer ? <p className="text-sm text-muted-foreground">{investigation.answer}</p> : null}

          <div className="mt-3 flex flex-wrap gap-2">
            {investigation.componentIds.map((componentId) => (
              <Badge
                key={componentId}
                variant="outline"
                className="rounded-full border-border/60 text-[11px] text-muted-foreground"
              >
                {componentId}
              </Badge>
            ))}
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">Evidence</p>
              <EvidencePreview evidence={investigation.evidence} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">Tool runs</p>
              <ToolRunPreview toolRuns={investigation.toolRuns} />
            </div>
          </div>
        </div>
      );
      })}
    </div>
  );
}

function EvidencePreview({ evidence }: { evidence: Investigation["evidence"] }) {
  if (!evidence.length) {
    return <p className="text-sm text-muted-foreground">Evidence pending or not recorded.</p>;
  }
  return (
    <ul className="space-y-2 text-sm text-muted-foreground">
      {evidence.slice(0, 3).map((item) => (
        <li key={item.evidenceId ?? item.url} className="flex items-center justify-between gap-3">
          <div>
            <div className="font-medium text-foreground">{item.title}</div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground/80">{item.source ?? "unknown"}</p>
          </div>
          {item.url ? (
            <Button variant="outline" size="sm" className="rounded-full text-xs" asChild>
              <Link href={item.url} target="_blank">
                View
              </Link>
            </Button>
          ) : null}
        </li>
      ))}
      {evidence.length > 3 ? (
        <p className="text-xs text-muted-foreground/80">+{evidence.length - 3} more evidence items</p>
      ) : null}
    </ul>
  );
}

function ToolRunPreview({ toolRuns }: { toolRuns: Investigation["toolRuns"] }) {
  if (!toolRuns.length) {
    return <p className="text-sm text-muted-foreground">No external tools recorded.</p>;
  }
  return (
    <ul className="space-y-1 text-sm text-muted-foreground">
      {toolRuns.slice(0, 3).map((run, index) => (
        <li key={run.stepId ?? `${run.tool}-${index}`} className="flex items-center justify-between gap-3">
          <div>
            <div className="font-medium text-foreground">{run.tool}</div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground/80">{run.status ?? "completed"}</p>
          </div>
          {run.outputPreview ? (
            <p className="max-w-[220px] text-xs italic text-muted-foreground/80">{run.outputPreview}</p>
          ) : null}
        </li>
      ))}
      {toolRuns.length > 3 ? (
        <p className="text-xs text-muted-foreground/80">+{toolRuns.length - 3} more tool steps</p>
      ) : null}
    </ul>
  );
}

