import { NextResponse } from "next/server";

import type { ContextFeedback } from "@/lib/context/types";

export async function POST(request: Request) {
  let payload: ContextFeedback;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload" }, { status: 400 });
  }

  if (!payload?.snippetId) {
    return NextResponse.json({ error: "snippetId is required" }, { status: 400 });
  }

  console.info("[context-feedback]", {
    snippetId: payload.snippetId,
    dismissed: payload.dismissed ?? false,
    projectId: payload.projectId,
    issueId: payload.issueId,
    componentId: payload.componentId,
  });

  return NextResponse.json({ ok: true });
}

