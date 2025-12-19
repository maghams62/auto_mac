import type { ExternalResult } from "@/lib/clients/types";
import { projects as mockProjects } from "@/lib/mock-data";
import { getIssueProvider, syntheticIssueProvider } from "@/lib/issues/providers";
import type { IssueProvider } from "@/lib/issues/providers/types";
import { allowSyntheticFallback, parseLiveMode } from "@/lib/mode";
import { jsonOk } from "@/lib/server/api-response";
import type { DocIssue } from "@/lib/types";

const DEFAULT_PROJECT_ID = mockProjects[0]?.id ?? null;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId") ?? DEFAULT_PROJECT_ID;
  const forcedMode = parseLiveMode(searchParams.get("mode"));
  const syntheticRequested = forcedMode === "synthetic";
  const syntheticFallbackEnabled = syntheticRequested || allowSyntheticFallback();

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

  const provider = getIssueProvider(syntheticRequested ? "synthetic" : null);
  const dependencies: Record<string, ExternalResult<unknown>> = {};

  const primary = await callIssueProvider(provider, projectId);
  dependencies.primary = primary;

  if (primary.status === "OK" && primary.data) {
    return jsonOk({
      status: "OK",
      mode: provider.name === "cerebros" ? "atlas" : "synthetic",
      data: {
        ...primary.data,
        provider: provider.name,
        fallback: false,
      },
      dependencies,
    });
  }

  if (provider.name !== "synthetic" && syntheticFallbackEnabled) {
    const fallbackProvider = syntheticIssueProvider;
    const fallback = await callIssueProvider(fallbackProvider, projectId);
    dependencies.fallback = fallback;
    if (fallback.status === "OK" && fallback.data) {
      return jsonOk({
        status: "UNAVAILABLE",
        fallbackReason: "primary_provider_failed",
        mode: "synthetic",
        data: {
          ...fallback.data,
          provider: "synthetic",
          fallback: true,
          fallbackProvider: provider.name,
        },
        dependencies,
        error: primary.error ?? {
          type: "UNKNOWN",
          message: "Primary issue provider failed",
        },
      });
    }
  }

  return jsonOk({
    status: "UNAVAILABLE",
    mode: "error",
    data: null,
    dependencies,
    error: primary.error ?? {
      type: "UNKNOWN",
      message: "Unable to load issues",
    },
  });
}

async function callIssueProvider(provider: IssueProvider, projectId: string): Promise<ExternalResult<{ projectId: string; issues: DocIssue[]; updatedAt: string }>> {
  try {
    const result = await provider.fetchIssues(projectId);
    return {
      status: "OK",
      data: result,
      meta: {
        provider: provider.name,
        endpoint: "issues",
      },
    };
  } catch (error) {
    return {
      status: "UNAVAILABLE",
      data: null,
      error: {
        type: "UNKNOWN",
        message: error instanceof Error ? error.message : "Issue provider failed",
      },
      meta: {
        provider: provider.name,
        endpoint: "issues",
      },
    };
  }
}

