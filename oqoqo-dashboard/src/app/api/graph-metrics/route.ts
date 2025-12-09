import { getGraphProvider, syntheticGraphProvider } from "@/lib/graph/providers";
import { parseLiveMode } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import type { ExternalResult } from "@/lib/clients/types";
import type { GraphMetrics } from "@/lib/graph/live-types";
import type { GraphProvider } from "@/lib/graph/providers";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const forcedMode = parseLiveMode(searchParams.get("mode"));
  const provider = getGraphProvider(forcedMode ?? null);
  const dependencies: Record<string, ExternalResult<unknown>> = {};

  const primary = await callGraphMetrics(provider);
  dependencies.primary = primary;

  if (primary.status === "OK" && primary.data) {
    return jsonOk({
      status: "OK",
      data: {
        provider: provider.name,
        metrics: primary.data,
        fallback: false,
      },
      dependencies,
    });
  }

  if (provider.name !== "synthetic") {
    const fallback = await callGraphMetrics(syntheticGraphProvider);
    dependencies.fallback = fallback;
    if (fallback.status === "OK" && fallback.data) {
      return jsonOk({
        status: "UNAVAILABLE",
        fallbackReason: "primary_provider_failed",
        data: {
          provider: "synthetic",
          fallback: true,
          fallbackProvider: provider.name,
          metrics: fallback.data,
        },
        dependencies,
        error: primary.error ?? {
          type: "UNKNOWN",
          message: "Primary graph metrics provider failed",
        },
      });
    }
  }

  return jsonOk({
    status: "UNAVAILABLE",
    data: null,
    dependencies,
    error: primary.error ?? {
      type: "UNKNOWN",
      message: "Unable to fetch graph metrics",
    },
  });
}

async function callGraphMetrics(provider: GraphProvider): Promise<ExternalResult<GraphMetrics>> {
  try {
    const metrics = await provider.fetchMetrics();
    return {
      status: "OK",
      data: metrics,
      meta: {
        provider: provider.name,
        endpoint: "graph/metrics",
      },
    };
  } catch (error) {
    return {
      status: "UNAVAILABLE",
      data: null,
      error: {
        type: "UNKNOWN",
        message: error instanceof Error ? error.message : "Graph metrics provider failed",
      },
      meta: {
        provider: provider.name,
        endpoint: "graph/metrics",
      },
    };
  }
}

