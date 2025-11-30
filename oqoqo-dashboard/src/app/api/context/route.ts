import { NextResponse } from "next/server";

import type { ContextRequest } from "@/lib/context/types";
import { getContextProvider, syntheticContextProvider } from "@/lib/context/providers";

export async function POST(request: Request) {
  let payload: ContextRequest;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload" }, { status: 400 });
  }

  if (!payload?.projectId) {
    return NextResponse.json({ error: "projectId is required" }, { status: 400 });
  }

  const provider = getContextProvider();

  try {
    const response = await provider.fetchContext(payload);
    return NextResponse.json({ ...response, fallback: false });
  } catch (error) {
    console.error("[context] primary provider failed", error);
    if (provider.name !== "synthetic") {
      try {
        const fallback = await syntheticContextProvider.fetchContext(payload);
        return NextResponse.json({
          ...fallback,
          fallback: true,
          fallbackProvider: provider.name,
        });
      } catch (fallbackError) {
        console.error("[context] fallback provider also failed", fallbackError);
      }
    }
    return NextResponse.json({ error: "Unable to load context snippets" }, { status: 500 });
  }
}

