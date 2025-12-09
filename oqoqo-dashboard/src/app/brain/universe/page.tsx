import { redirect } from "next/navigation";

const DEFAULT_TARGET = "http://localhost:3300/brain/neo4j/";

export default function BrainUniverseRedirectPage() {
  const target = process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL?.trim() || DEFAULT_TARGET;
  redirect(target);
}

