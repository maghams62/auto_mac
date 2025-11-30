import { NextResponse } from "next/server";

import { projects as mockProjects } from "@/lib/mock-data";
import { getIssueProvider, syntheticIssueProvider } from "@/lib/issues/providers";

const DEFAULT_PROJECT_ID = mockProjects[0]?.id ?? null;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId") ?? DEFAULT_PROJECT_ID;

  if (!projectId) {
    return NextResponse.json({ error: "projectId is required" }, { status: 400 });
  }

  const provider = getIssueProvider();

  try {
    const result = await provider.fetchIssues(projectId);
    return NextResponse.json({ ...result, fallback: false });
  } catch (error) {
    console.error("[issues] primary provider failed", error);
    if (provider.name !== "synthetic") {
      try {
        const fallback = await syntheticIssueProvider.fetchIssues(projectId);
        return NextResponse.json({
          ...fallback,
          fallback: true,
          fallbackProvider: provider.name,
        });
      } catch (fallbackError) {
        console.error("[issues] fallback provider failed", fallbackError);
      }
    }
    return NextResponse.json({ error: "Unable to load issues" }, { status: 500 });
  }
}

