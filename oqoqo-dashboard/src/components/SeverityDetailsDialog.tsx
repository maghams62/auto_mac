import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { SeverityExplanation } from "@/lib/types";

type SeverityDetailsDialogProps = {
  open: boolean;
  onClose: () => void;
  severityLabel: string;
  severityScore?: number;
  explanation?: SeverityExplanation;
  breakdown?: Record<string, number>;
  weights?: Record<string, number>;
  contributions?: Record<string, number>;
};

const CORE_MODALITIES = ["slack", "git", "doc", "semantic", "graph"] as const;
const SECONDARY_SECTIONS = ["slack", "git", "doc", "semantic", "graph", "syntactic", "relationship"] as const;

export default function SeverityDetailsDialog({
  open,
  onClose,
  severityLabel,
  severityScore,
  explanation,
  breakdown,
  weights,
  contributions,
}: SeverityDetailsDialogProps) {
  if (!explanation) {
    return null;
  }

  const inputs = explanation.inputs ?? {};
  const backendScore = typeof explanation.final?.score_0_1 === "number" ? explanation.final.score_0_1 : undefined;
  const recomputedScore = computeRecomputedScore(breakdown, weights);
  const mismatch =
    backendScore !== undefined &&
    recomputedScore !== undefined &&
    Math.abs(backendScore - recomputedScore) > 0.01;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-hidden">
        <DialogHeader>
          <DialogTitle>Severity math breakdown</DialogTitle>
          <DialogDescription>
            {explanation.formula} · Severity {severityLabel.toUpperCase()}{" "}
            {typeof severityScore === "number" ? `(${severityScore.toFixed(1)} / 10)` : ""}
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[75vh] pr-2">
          <div className="space-y-6 text-sm text-foreground">
            <section className="space-y-3 rounded-2xl border border-border/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Weighted contributions
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-3">Modality</th>
                      <th className="py-2 pr-3">Score (0-1)</th>
                      <th className="py-2 pr-3">Weight</th>
                      <th className="py-2">Contribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {CORE_MODALITIES.map((key) => {
                      const input = inputs[key];
                      if (!input) {
                        return null;
                      }
                      const label = input.label ?? key;
                      const score = selectNumber(input.score);
                      const weight = selectNumber(input.weight ?? weights?.[key]);
                      const contribution = selectNumber(input.contribution ?? contributions?.[key]);
                      return (
                        <tr key={key} className="border-t border-border/20">
                          <td className="py-2 pr-3 font-medium">{label}</td>
                          <td className="py-2 pr-3 font-mono text-xs">{formatNumber(score)}</td>
                          <td className="py-2 pr-3 font-mono text-xs">{formatNumber(weight)}</td>
                          <td className="py-2 font-mono text-xs">{formatNumber(contribution)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Separator className="bg-border/40" />
              <div className="text-xs text-muted-foreground">
                <p>Σ(weight × score) = {backendScore !== undefined ? backendScore.toFixed(4) : "n/a"}</p>
                {recomputedScore !== undefined ? (
                  <p>
                    Recomputed from breakdown = {recomputedScore.toFixed(4)}{" "}
                    {mismatch ? (
                      <span className="ml-2 text-amber-400">⚠ mismatch – verify severity inputs</span>
                    ) : (
                      <span className="ml-2 text-emerald-300">✓ matches backend value</span>
                    )}
                  </p>
                ) : null}
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Per-modality terms
              </h3>
              <div className="space-y-3">
                {SECONDARY_SECTIONS.map((key) => {
                  const input = inputs[key];
                  if (!input) {
                    return null;
                  }
                  return <TermsDisclosure key={key} modalityKey={key} input={input} />;
                })}
              </div>
            </section>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

function TermsDisclosure({
  modalityKey,
  input,
}: {
  modalityKey: string;
  input: SeverityExplanation["inputs"][string];
}) {
  const termsEntries = Object.entries(input?.terms ?? {});
  const hasTerms = termsEntries.length > 0;
  return (
    <details className="rounded-2xl border border-border/40 bg-background/80 p-4" open={modalityKey === "slack"}>
      <summary className="cursor-pointer list-none font-semibold">
        {input?.label ?? modalityKey} · score {formatNumber(input?.score)}{" "}
        {typeof input?.weight === "number" ? `· weight ${formatNumber(input.weight)}` : ""}{" "}
        {typeof input?.contribution === "number" ? `· contribution ${formatNumber(input.contribution)}` : ""}
      </summary>
      <div className="mt-3 space-y-3 text-xs">
        {input?.definition ? <p className="text-muted-foreground">{input.definition}</p> : null}
        {input?.components ? (
          <div>
            <p className="mb-1 font-semibold text-muted-foreground">Component scores</p>
            <div className="grid grid-cols-2 gap-2 rounded-xl border border-border/40 p-3 text-foreground">
              {Object.entries(input.components).map(([name, value]) => (
                <div key={name} className="flex items-center justify-between">
                  <span className="capitalize text-muted-foreground">{name}</span>
                  <span className="font-mono text-sm">{formatNumber(value)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {hasTerms ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                  <th className="py-1 pr-4">Term</th>
                  <th className="py-1">Value</th>
                </tr>
              </thead>
              <tbody>
                {termsEntries.map(([termKey, value]) => (
                  <tr key={termKey} className="border-t border-border/20">
                    <td className="py-1 pr-4 font-medium">{termKey.replace(/_/g, " ")}</td>
                    <td className="py-1 font-mono text-[11px]">{formatTermValue(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted-foreground">No term-level metrics were reported for this modality.</p>
        )}
        {input?.raw_features ? (
          <div>
            <p className="mb-1 font-semibold text-muted-foreground">Raw features</p>
            <pre className="max-h-48 overflow-auto rounded-xl border border-border/30 bg-black/40 p-3 text-[11px] text-emerald-100">
              {JSON.stringify(input.raw_features, null, 2)}
            </pre>
          </div>
        ) : null}
      </div>
    </details>
  );
}

function computeRecomputedScore(
  breakdown?: Record<string, number>,
  weights?: Record<string, number>,
): number | undefined {
  if (!breakdown || !weights) {
    return undefined;
  }
  const value = CORE_MODALITIES.reduce((sum, key) => {
    const score = breakdown[key];
    const weight = weights[key];
    if (typeof score !== "number" || typeof weight !== "number") {
      return sum;
    }
    return sum + weight * score;
  }, 0);
  return value;
}

function formatNumber(value?: number): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(4);
}

function selectNumber(value?: number | null): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function formatTermValue(value: unknown): string {
  if (typeof value === "number") {
    return value.toFixed(4);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (Array.isArray(value)) {
    return JSON.stringify(value);
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}
