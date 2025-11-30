import { NextResponse } from "next/server";

import { getIngestionConfig } from "@/lib/config";

export async function GET() {
  const config = getIngestionConfig();
  if (!config) {
    return NextResponse.json({ error: "Missing ingestion config" }, { status: 500 });
  }

  return NextResponse.json(config);
}

