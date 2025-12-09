import { getGraphProvider, syntheticGraphProvider } from "@/lib/graph/providers";
import { projects as mockProjects } from "@/lib/mock-data";
import { parseLiveMode } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import type { ExternalResult } from "@/lib/clients/types";

import type { GraphProvider, GraphProviderResult } from "@/lib/graph/providers";

const DEFAULT_PROJECT_ID = mockProjects[0]?.id ?? null;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId") ?? DEFAULT_PROJECT_ID;
  const forcedMode = parseLiveMode(searchParams.get("mode"));

  if (!projectId) {
    return jsonOk({
      status: "NOT_FOUND",
      data: null,
      error: {
        type: "INVALID_RESPONSE",
        message: "projectId is required",
      },
    });
  }

  const provider = getGraphProvider(forcedMode ?? null);
  const dependencies: Record<string, ExternalResult<unknown>> = {};

  const primary = await callGraphProvider(provider, projectId);
  dependencies.primary = primary;

  if (primary.status === "OK" && primary.data) {
    return jsonOk({
      status: "OK",
      data: {
        ...primary.data,
        fallback: false,
      },
      dependencies,
    });
  }

  if (provider.name !== "synthetic") {
    const fallback = await callGraphProvider(syntheticGraphProvider, projectId);
    dependencies.fallback = fallback;
    if (fallback.status === "OK" && fallback.data) {
      return jsonOk({
        status: "UNAVAILABLE",
        fallbackReason: "primary_provider_failed",
        data: {
          ...fallback.data,
          fallback: true,
          fallbackProvider: provider.name,
        },
        dependencies,
        error: primary.error ?? {
          type: "UNKNOWN",
          message: "Primary graph provider failed",
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
      message: "Unable to fetch graph snapshot",
    },
  });
}

async function callGraphProvider(provider: GraphProvider, projectId: string): Promise<ExternalResult<GraphProviderResult>> {
  try {
    const result = await provider.fetchSnapshot(projectId);
    return {
      status: "OK",
      data: result,
      meta: {
        provider: provider.name,
        endpoint: "graph/snapshot",
      },
    };
  } catch (error) {
    return {
      status: "UNAVAILABLE",
      data: null,
      error: {
        type: "UNKNOWN",
        message: error instanceof Error ? error.message : "Graph provider failed",
      },
      meta: {
        provider: provider.name,
        endpoint: "graph/snapshot",
      },
    };
  }
}

