import { redirect } from "next/navigation";

const TARGET_URL = process.env.NEXT_PUBLIC_BRAIN_GRAPH_URL?.trim() || "http://localhost:3300/brain/neo4j/";

export default function BrainNeo4jRedirectPage() {
  redirect(TARGET_URL);
}

