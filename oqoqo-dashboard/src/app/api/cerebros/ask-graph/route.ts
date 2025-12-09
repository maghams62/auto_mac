// Restored after accidental deletion – bridge between Graph UI and Cerebros graph reasoner
import { NextResponse } from "next/server";

import { requestCerebrosJson } from "@/lib/clients/cerebros";

const GRAPH_REASONER_PATH = "/api/graph/query";

type GraphAskRequest = {
  query: string;
  graphParams?: Record<string, unknown>;
};

export async function POST(request: Request) {
  let payload: GraphAskRequest;
  try {
    payload = (await request.json()) as GraphAskRequest;
  } catch (error) {
    console.warn("[cerebros/ask-graph] invalid JSON body", error);
    return NextResponse.json({ error: "Invalid JSON payload" }, { status: 400 });
  }

  if (!payload?.query) {
    return NextResponse.json({ error: "query is required" }, { status: 400 });
  }

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };

  const authHeader = request.headers.get("authorization");
  if (authHeader) {
    headers.Authorization = authHeader;
  }

  const timeoutMs = Math.max(Number(process.env.CEREBROS_TIMEOUT_MS ?? 60_000), 15_000);
  const result = await requestCerebrosJson<unknown>(GRAPH_REASONER_PATH, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query: payload.query,
      graphParams: payload.graphParams ?? {},
    }),
    timeoutMs,
  });

  if (result.status === "OK" && result.data) {
    return NextResponse.json(result.data, { status: 200 });
  }

  const statusCode = result.error?.statusCode ?? 502;
  const message = result.error?.message ?? "Cerebros graph endpoint failed";
  return NextResponse.json({ error: message }, { status: statusCode });
}

export async function GET() {
  return NextResponse.json(
    {
      status: "METHOD_NOT_ALLOWED",
      message: "POST a JSON payload containing { query, graphParams } to run Ask Cerebros.",
    },
    { status: 405 },
  );
}


