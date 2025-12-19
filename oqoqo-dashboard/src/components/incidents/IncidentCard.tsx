import Link from "next/link";

import { DeepLinkButtons } from "@/components/common/deep-link-buttons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { collectComponentIds, collectServiceIds, deriveIncidentLinks } from "@/lib/incidents/helpers";
import type { IncidentRecord } from "@/lib/types";
import { severityTokens } from "@/lib/ui/tokens";
import { cn, longDateTime } from "@/lib/utils";

type IncidentCardProps = {
  incident: IncidentRecord;
};

const summaryFallback = (incident: IncidentRecord) =>
  incident.summary ||
  incident.question ||
  incident.rootCauseExplanation ||
  incident.impactSummary ||
  incident.answer ||
  "Incident";

export function IncidentCard({ incident }: IncidentCardProps) {
  const severity = severityTokens[incident.severity] ?? severityTokens["medium"];
  const title = summaryFallback(incident);
  const blurb =
    incident.impactSummary ||
    incident.rootCauseExplanation ||
    incident.answer ||
    incident.llmExplanation ||
    incident.summary ||
    "";
  const detectedAt = longDateTime(incident.createdAt);
  const componentIds = collectComponentIds(incident).slice(0, 4);
  const serviceIds = collectServiceIds(incident).slice(0, 4);
  const linkTargets = deriveIncidentLinks(incident);

  return (
    <div className="space-y-4 rounded-2xl border border-border/60 bg-background/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-[11px] text-muted-foreground">Detected · {detectedAt}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge className={cn("border text-[10px] uppercase", severity.color)}>{severity.label}</Badge>
          <Badge variant="outline" className="rounded-full border-border/50 text-[10px] uppercase">
            {incident.status}
          </Badge>
          {incident.projectId ? (
            <Badge variant="outline" className="rounded-full border-border/40 text-[10px] uppercase">
              {incident.projectId}
            </Badge>
          ) : null}
        </div>
      </div>

      {blurb ? <p className="text-sm text-muted-foreground line-clamp-3">{blurb}</p> : null}

      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        {componentIds.map((id) => (
          <Badge key={id} variant="outline" className="rounded-full border-border/40 text-[10px] uppercase">
            {id}
          </Badge>
        ))}
        {serviceIds.map((id) => (
          <Badge
            key={`svc-${id}`}
            variant="outline"
            className="rounded-full border-slate-500/40 text-[10px] uppercase text-slate-200"
          >
            {id}
          </Badge>
        ))}
        {incident.blastRadiusScore !== undefined ? (
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/5 px-3 py-1 text-[10px] font-semibold text-emerald-200">
            Blast radius · {Math.round(incident.blastRadiusScore)}
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <DeepLinkButtons
          githubUrl={linkTargets.githubUrl}
          slackUrl={linkTargets.slackUrl}
          docUrl={linkTargets.docUrl}
          cerebrosUrl={linkTargets.cerebrosUrl}
          size="sm"
        />
        <Button asChild size="sm" variant="secondary" className="rounded-full px-4 text-xs uppercase tracking-wide">
          <Link href={`/incidents/${incident.id}`}>View incident</Link>
        </Button>
      </div>
    </div>
  );
}
