import type { IncidentEntity, IncidentRecord } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { EvidenceLookup } from "./evidence-utils";
import { resolveEvidenceHref } from "./evidence-utils";

const chipBaseClass =
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide";

interface IncidentReportTableProps {
  incident: IncidentRecord;
  evidenceLookup: EvidenceLookup;
}

export default function IncidentReportTable({ incident, evidenceLookup }: IncidentReportTableProps) {
  const entities = incident.incidentEntities;

  if (!entities || entities.length === 0) {
    return (
      <section className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Incident report</h2>
          <p className="text-xs text-muted-foreground">
            Impacted components, docs, and tickets will appear here once structured data is available.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded-3xl border border-border/50 bg-background/70 p-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Incident report</h2>
          <p className="text-xs text-muted-foreground">
            Each row highlights an impacted entity plus the recommended follow-up.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {entities.length} impacted {entities.length === 1 ? "entity" : "entities"}
        </p>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-border/20">
        <table className="min-w-[720px] divide-y divide-border/40 text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-muted-foreground/80">
              <th className="px-3 py-2 text-left">Entity</th>
              <th className="px-3 py-2 text-left">Activity</th>
              <th className="px-3 py-2 text-left">Dissatisfaction</th>
              <th className="px-3 py-2 text-left">Doc / Drift</th>
              <th className="px-3 py-2 text-left">Dependency</th>
              <th className="px-3 py-2 text-left">Suggested action</th>
              <th className="px-3 py-2 text-left">Evidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20 text-sm">
            {entities.map((entity) => (
              <tr key={`${entity.entityType}-${entity.id}`} className="align-top">
                <td className="px-3 py-3">
                  <div className="flex flex-col gap-1">
                    <span className="font-semibold text-foreground">{entity.name}</span>
                    <span className="text-xs text-muted-foreground capitalize">{entity.entityType}</span>
                  </div>
                </td>
                <td className="px-3 py-3">
                  <SignalStack signals={entity.activitySignals} tone="activity" emptyLabel="—" />
                </td>
                <td className="px-3 py-3">
                  <SignalStack signals={entity.dissatisfactionSignals} tone="dissatisfaction" emptyLabel="—" />
                </td>
                <td className="px-3 py-3">
                  {entity.docStatus ? (
                    <div className="space-y-1">
                      {entity.docStatus.severity ? (
                        <Badge variant="outline" className="rounded-full border-amber-500/40 text-amber-200">
                          {entity.docStatus.severity}
                        </Badge>
                      ) : null}
                      {entity.docStatus.reason ? (
                        <p className="text-xs text-muted-foreground">{entity.docStatus.reason}</p>
                      ) : null}
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-3 py-3">
                  {entity.dependency ? (
                    <DependencySummary dependency={entity.dependency} />
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-3 py-3">
                  {entity.suggestedAction ? (
                    <p className="text-xs text-foreground">{entity.suggestedAction}</p>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-3 py-3">
                  <EvidenceLinks evidenceIds={entity.evidenceIds} evidenceLookup={evidenceLookup} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SignalStack({
  signals,
  tone,
  emptyLabel = "–",
}: {
  signals?: Record<string, number>;
  tone: "activity" | "dissatisfaction";
  emptyLabel?: string;
}) {
  if (!signals || Object.keys(signals).length === 0) {
    return <span className="text-xs text-muted-foreground">{emptyLabel}</span>;
  }
  const badgeClass =
    tone === "activity" ? "border-emerald-500/40 text-emerald-100" : "border-rose-500/40 text-rose-100";
  const seen = new Set<string>();
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.entries(signals)
        .filter(([, value]) => typeof value === "number" && value > 0)
        .map(([label, value]) => {
          const normalized = label.toLowerCase();
          if (seen.has(normalized)) {
            return null;
          }
          seen.add(normalized);
          return (
            <span key={label} className={cn(chipBaseClass, badgeClass)}>
              {label.replace(/_/g, " ")} · {value}
            </span>
          );
        })}
    </div>
  );
}

function DependencySummary({
  dependency,
}: {
  dependency: IncidentEntity["dependency"];
}) {
  if (!dependency) return null;
  return (
    <div className="space-y-1 text-xs text-foreground">
      {dependency.dependentComponents && dependency.dependentComponents.length ? (
        <p>
          ↳ {dependency.dependentComponents.slice(0, 3).join(", ")}
          {dependency.dependentComponents.length > 3 ? "…" : ""}
        </p>
      ) : null}
      {dependency.docs && dependency.docs.length ? (
        <p className="text-muted-foreground">
          Docs: {dependency.docs.slice(0, 3).join(", ")}
          {dependency.docs.length > 3 ? "…" : ""}
        </p>
      ) : null}
      {dependency.depth !== undefined ? (
        <p className="text-muted-foreground">Depth {dependency.depth}</p>
      ) : null}
    </div>
  );
}

function EvidenceLinks({
  evidenceIds,
  evidenceLookup,
}: {
  evidenceIds?: string[];
  evidenceLookup: EvidenceLookup;
}) {
  if (!evidenceIds || evidenceIds.length === 0) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  return (
    <div className="flex flex-col gap-1.5">
      {evidenceIds.map((id) => {
        const entry = evidenceLookup.get(id) ?? evidenceLookup.get(String(id));
        if (!entry) {
          return (
            <span key={id} className="text-[11px] text-muted-foreground">
              {id}
            </span>
          );
        }
        const label = entry.item.title || entry.item.source || id;
        const inlineHref = entry.anchorId ? `#${entry.anchorId}` : undefined;
        const directHref = resolveEvidenceHref(entry.item);
        return (
          <div key={id} className="flex items-center justify-between gap-2">
            <span className="truncate text-[11px] text-muted-foreground">{label}</span>
            {directHref ? (
              <Button asChild variant="outline" size="sm" className="rounded-full text-[11px]">
                <Link href={directHref} target="_blank" rel="noreferrer">
                  Open ↗
                </Link>
              </Button>
            ) : inlineHref ? (
              <Button asChild variant="outline" size="sm" className="rounded-full text-[11px]">
                <Link href={inlineHref}>
                  View ↗
                </Link>
              </Button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
