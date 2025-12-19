import { promises as fs } from "fs";
import path from "path";

import type { InvestigationEvidence, SeverityExplanation } from "@/lib/types";

export type TraceabilityIncident = {
  id?: string;
  type?: string;
  summary?: string;
  question?: string;
  answer?: string;
  llm_explanation?: string;
  severity?: string;
  status?: string;
  blast_radius_score?: number;
  source_command?: string;
  raw_trace_id?: string;
  project_id?: string;
  component_ids?: string[];
  created_at?: string;
  incident_context?: {
    counts?: Record<string, number>;
    impacted_nodes?: Record<string, unknown>;
    recency_info?: Record<string, unknown>;
  };
  root_cause_explanation?: string;
  impact_summary?: string;
  resolution_plan?: string | string[];
  activity_signals?: Record<string, number>;
  dissatisfaction_signals?: Record<string, number>;
  dependency_impact?: Record<string, unknown>;
  doc_priorities?: Array<Record<string, unknown>>;
  activity_score?: number;
  dissatisfaction_score?: number;
  graph_query?: Record<string, unknown>;
  source_divergence?: Record<string, unknown>;
  information_gaps?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
  brainTraceUrl?: string;
  brainUniverseUrl?: string;
  evidence?: InvestigationEvidence[];
  incident_entities?: Array<Record<string, unknown>>;
  severity_payload?: Record<string, unknown>;
  severity_score?: number;
  severity_score_100?: number;
  severity_breakdown?: Record<string, number>;
  severity_details?: Record<string, unknown>;
  severity_contributions?: Record<string, number>;
  severity_weights?: Record<string, number>;
  severity_semantic_pairs?: Record<string, unknown>;
  severity_explanation?: SeverityExplanation;
};

export type TraceabilityStoreMeta = {
  path: string;
  totalRecords: number;
  incidentsAvailable: number;
  lastModified?: string | null;
  error?: string;
};

type IncidentFilters = {
  limit: number;
  projectId?: string;
  componentId?: string;
  severity?: string;
  status?: string;
  since?: string;
};

const TRACEABILITY_LOG_PATH =
  process.env.TRACEABILITY_LOG_PATH && process.env.TRACEABILITY_LOG_PATH.trim().length
    ? path.resolve(process.cwd(), process.env.TRACEABILITY_LOG_PATH.trim())
    : path.resolve(process.cwd(), "../data/live/investigations.jsonl");

let hasLoggedMissingStore = false;

export function getTraceabilitySourcePath() {
  return TRACEABILITY_LOG_PATH;
}

export async function listTraceabilityIncidents(filters: IncidentFilters): Promise<{
  incidents: TraceabilityIncident[];
  meta: TraceabilityStoreMeta;
}> {
  const { records, meta } = await readTraceabilityRecords();
  const incidentsOnly = records
    .filter((record) => (record.type ?? "investigation") === "incident")
    .sort((a, b) => compareDate(b.created_at) - compareDate(a.created_at));

  const filtered = applyFilters(incidentsOnly, filters);

  return {
    incidents: filtered.slice(0, filters.limit),
    meta: {
      ...meta,
      incidentsAvailable: incidentsOnly.length,
    },
  };
}

export async function findTraceabilityIncidentById(incidentId: string): Promise<{
  incident: TraceabilityIncident | null;
  meta: TraceabilityStoreMeta;
}> {
  const { records, meta } = await readTraceabilityRecords();
  const incident = records
    .filter((record) => (record.type ?? "investigation") === "incident")
    .find((record) => record.id === incidentId);

  return {
    incident: incident ?? null,
    meta: {
      ...meta,
      incidentsAvailable: meta.incidentsAvailable ?? records.length,
    },
  };
}

async function readTraceabilityRecords(): Promise<{
  records: TraceabilityIncident[];
  meta: TraceabilityStoreMeta;
}> {
  try {
    const raw = await fs.readFile(TRACEABILITY_LOG_PATH, "utf-8");
    const parsed = parseTraceabilityPayload(raw);
    const stat = await fs.stat(TRACEABILITY_LOG_PATH);
    return {
      records: parsed,
      meta: {
        path: TRACEABILITY_LOG_PATH,
        totalRecords: parsed.length,
        incidentsAvailable: parsed.filter((record) => (record.type ?? "investigation") === "incident").length,
        lastModified: stat.mtime.toISOString(),
      },
    };
  } catch (error) {
    if (!hasLoggedMissingStore) {
      console.warn("[traceability-store] failed to read traceability log", {
        path: TRACEABILITY_LOG_PATH,
        error,
      });
      hasLoggedMissingStore = true;
    }
    return {
      records: [],
      meta: {
        path: TRACEABILITY_LOG_PATH,
        totalRecords: 0,
        incidentsAvailable: 0,
        error: error instanceof Error ? error.message : "unknown error",
      },
    };
  }
}

function parseTraceabilityPayload(raw: string): TraceabilityIncident[] {
  const trimmed = raw.trim();
  if (!trimmed.length) {
    return [];
  }

  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      return parsed as TraceabilityIncident[];
    }
  } catch (error) {
    // Fallback to JSONL-style entries when JSON parsing fails.
    const lines = trimmed.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const fallback: TraceabilityIncident[] = [];
    for (const line of lines) {
      try {
        const entry = JSON.parse(line);
        fallback.push(entry as TraceabilityIncident);
      } catch (lineError) {
        console.warn("[traceability-store] skipped malformed line", {
          path: TRACEABILITY_LOG_PATH,
          line,
          error: lineError,
        });
      }
    }
    return fallback;
  }

  return [];
}

function applyFilters(records: TraceabilityIncident[], filters: IncidentFilters): TraceabilityIncident[] {
  let incidents = records;

  if (filters.projectId) {
    incidents = incidents.filter((record) => record.project_id === filters.projectId);
  }

  if (filters.componentId) {
    const target = filters.componentId.toLowerCase();
    incidents = incidents.filter((record) =>
      (record.component_ids ?? []).some((component) => component?.toLowerCase() === target),
    );
  }

  if (filters.severity) {
    const target = filters.severity.toLowerCase();
    incidents = incidents.filter((record) => (record.severity ?? "").toLowerCase() === target);
  }

  if (filters.status) {
    const target = filters.status.toLowerCase();
    incidents = incidents.filter((record) => (record.status ?? "").toLowerCase() === target);
  }

  if (filters.since) {
    const cutoff = Date.parse(filters.since);
    if (!Number.isFinite(cutoff)) {
      throw new Error("since must be ISO-8601 timestamp");
    }
    incidents = incidents.filter((record) => compareDate(record.created_at) >= cutoff);
  }

  return incidents;
}

function compareDate(value?: string) {
  if (!value) {
    return 0;
  }
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : 0;
}
