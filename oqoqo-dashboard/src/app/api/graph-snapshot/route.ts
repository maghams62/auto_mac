import { NextResponse } from "next/server";

import { getGraphProvider, syntheticGraphProvider } from "@/lib/graph/providers";
import { projects as mockProjects } from "@/lib/mock-data";

const DEFAULT_PROJECT_ID = mockProjects[0]?.id ?? null;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId") ?? DEFAULT_PROJECT_ID;

  if (!projectId) {
    return NextResponse.json({ error: "projectId is required" }, { status: 400 });
  }

  const provider = getGraphProvider();

  try {
    const result = await provider.fetchSnapshot(projectId);
    return NextResponse.json({ ...result, fallback: false });
  } catch (error) {
    console.error("[graph-snapshot] primary provider failed", error);
    if (provider.name !== "synthetic") {
      try {
        const fallbackResult = await syntheticGraphProvider.fetchSnapshot(projectId);
        return NextResponse.json({
          ...fallbackResult,
          fallback: true,
          fallbackProvider: provider.name,
        });
      } catch (fallbackError) {
        console.error("[graph-snapshot] fallback provider also failed", fallbackError);
      }
    }
    return NextResponse.json({ error: "Unable to fetch graph snapshot" }, { status: 500 });
  }
}

