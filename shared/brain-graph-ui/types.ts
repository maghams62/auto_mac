export type GraphExplorerNode = {
  id: string;
  label: string;
  title?: string;
  labels?: string[];
  modality?: string;
  createdAt?: string;
  updatedAt?: string;
  props: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
};

export type GraphExplorerEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  createdAt?: string;
  props: Record<string, unknown>;
};

export type GraphExplorerMeta = {
  nodeLabelCounts: Record<string, number>;
  relTypeCounts: Record<string, number>;
  propertyKeys: string[];
  modalityCounts?: Record<string, number>;
  missingTimestampLabels?: string[];
  minTimestamp?: string | null;
  maxTimestamp?: string | null;
};

export type GraphExplorerResponse = {
  generatedAt: string;
  nodes: GraphExplorerNode[];
  edges: GraphExplorerEdge[];
  filters: Record<string, unknown>;
  meta: GraphExplorerMeta;
};

export type ExplorerFilters = {
  modalities: string[] | null;
  limit: number;
  snapshotAt?: string;
};

export type GraphRequestPhase = "idle" | "pending" | "success" | "error" | "aborted";

export type GraphRequestInfo = {
  target: string;
  status: GraphRequestPhase;
  startedAt: string;
  completedAt?: string;
  durationMs?: number;
  httpStatus?: number;
  errorMessage?: string;
  errorKind?: "network" | "http" | "timeout" | "aborted" | "unknown";
};

export type GraphApiDiagnostics = {
  baseUrl: string;
  source: string;
  healthUrl?: string;
  note?: string;
};

export type GraphExplorerProps = {
  mode?: "universe" | "issue" | "neo4j_default";
  rootNodeId?: string;
  depth?: number;
  projectId?: string;
  apiBaseUrl?: string;
  endpointPath?: string;
  initialFilters?: Partial<ExplorerFilters>;
  hideDatabasePanel?: boolean;
  className?: string;
  title?: string;
  enableTimeControls?: boolean;
  apiDiagnostics?: GraphApiDiagnostics;
  lockViewport?: boolean;
  layoutStyle?: "radial" | "neo4j";
  variant?: "default" | "neo4j";
};


