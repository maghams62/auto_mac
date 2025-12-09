import type { IngestStatusPayload } from "@/lib/types";
import { requestCerebrosJson } from "@/lib/clients/cerebros";
import { jsonOk } from "@/lib/server/api-response";

export async function GET() {
  const ingestStatus = await requestCerebrosJson<IngestStatusPayload>("/api/ingest/status", {
    timeoutMs: 3000,
  });

  return jsonOk({
    status: ingestStatus.status,
    data: ingestStatus.data ?? null,
    error: ingestStatus.error,
    dependencies: {
      ingestStatus,
    },
  });
}

