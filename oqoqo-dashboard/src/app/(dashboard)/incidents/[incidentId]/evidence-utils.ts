import type { InvestigationEvidence } from "@/lib/types";
import { buildDocLink, buildRepoLink } from "@/lib/link-builders";

export type EvidenceLookupEntry = {
  item: InvestigationEvidence;
  anchorId?: string;
};

export type EvidenceLookup = Map<string, EvidenceLookupEntry>;

const SAFE_ANCHOR_PATTERN = /[^a-z0-9]+/gi;

export function getEvidenceAnchorId(value: string, fallbackIndex?: number): string {
  const normalized = value
    .toLowerCase()
    .replace(SAFE_ANCHOR_PATTERN, "-")
    .replace(/^-+|-+$/g, "");
  const suffix = normalized || (typeof fallbackIndex === "number" ? `item-${fallbackIndex}` : "item");
  return `evidence-${suffix}`;
}

export function buildEvidenceLookup(evidenceItems: InvestigationEvidence[]): EvidenceLookup {
  const lookup: EvidenceLookup = new Map();
  evidenceItems.forEach((item, index) => {
    const key = String(item.evidenceId ?? item.title ?? `evidence-${index}`);
    const entry: EvidenceLookupEntry = {
      item,
      anchorId: getEvidenceAnchorId(String(item.evidenceId ?? key), index),
    };
    const keys = new Set<string>([key]);
    if (item.evidenceId) {
      keys.add(String(item.evidenceId));
    }
    if (item.title) {
      keys.add(String(item.title));
    }
    keys.forEach((alias) => {
      if (!lookup.has(alias)) {
        lookup.set(alias, entry);
      }
    });
  });
  return lookup;
}

export function resolveEvidenceHref(evidence: InvestigationEvidence): string | undefined {
  if (evidence.url && evidence.url.startsWith("http")) {
    return evidence.url;
  }
  if (evidence.url && evidence.url.startsWith("/")) {
    return evidence.url;
  }
  const metadata = (evidence.metadata as Record<string, unknown>) || {};
  const docPath = typeof metadata["doc_path"] === "string" ? (metadata["doc_path"] as string) : undefined;
  const docUrl = typeof metadata["doc_url"] === "string" ? (metadata["doc_url"] as string) : undefined;
  const repoPath = typeof metadata["repo_path"] === "string" ? (metadata["repo_path"] as string) : undefined;
  return buildDocLink(docUrl, docPath) ?? buildRepoLink(repoPath ?? undefined);
}


