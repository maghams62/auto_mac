export function formatTimestamp(value?: string) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const LABEL_COLORS: Record<string, string> = {
  Component: "#38bdf8",
  Service: "#22d3ee",
  APIEndpoint: "#f472b6",
  Doc: "#facc15",
  Issue: "#fb7185",
  PR: "#a3e635",
  GitEvent: "#34d399",
  Repository: "#94a3b8",
  Channel: "#67e8f9",
  Chunk: "#fcd34d",
  TranscriptChunk: "#d8b4fe",
  Source: "#e5e7eb",
  Playlist: "#c4b5fd",
  SlackThread: "#c084fc",
  SlackEvent: "#c084fc",
  ActivitySignal: "#f97316",
  SupportCase: "#fca5a5",
  ImpactEvent: "#fdba74",
};

const MODALITY_COLORS: Record<string, string> = {
  component: "#38bdf8",
  service: "#22d3ee",
  api: "#f472b6",
  doc: "#facc15",
  issue: "#fb7185",
  git: "#34d399",
  slack: "#c084fc",
  slackthread: "#c084fc",
  signal: "#f97316",
  support: "#fda4af",
  impact: "#fdba74",
  repo: "#94a3b8",
  repository: "#94a3b8",
  channel: "#67e8f9",
  chunk: "#fcd34d",
  transcriptchunk: "#d8b4fe",
  source: "#e5e7eb",
  playlist: "#c4b5fd",
};

export function getColorForNode(label: string, modality?: string) {
  if (modality && MODALITY_COLORS[modality]) {
    return MODALITY_COLORS[modality];
  }
  return LABEL_COLORS[label] || "#94a3b8";
}

export function resolveApiUrl(apiBaseUrl: string | undefined, endpointPath: string, searchParams: URLSearchParams) {
  if (apiBaseUrl) {
    const url = new URL(endpointPath, apiBaseUrl.endsWith("/") ? apiBaseUrl : `${apiBaseUrl}/`);
    url.search = searchParams.toString();
    return url.toString();
  }
  const relative = endpointPath.startsWith("/") ? endpointPath : `/${endpointPath}`;
  return `${relative}?${searchParams.toString()}`;
}


