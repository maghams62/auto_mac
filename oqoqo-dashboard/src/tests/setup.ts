import "@testing-library/jest-dom/vitest";

process.env.GRAPH_MODE = process.env.GRAPH_MODE ?? "synthetic";
process.env.ISSUE_MODE = process.env.ISSUE_MODE ?? "synthetic";
process.env.OQOQO_MODE = process.env.OQOQO_MODE ?? "synthetic";
process.env.NEO4J_URI = "";
process.env.NEO4J_USER = "";
process.env.NEO4J_PASSWORD = "";
process.env.QDRANT_URL = "";
process.env.QDRANT_API_KEY = "";
delete process.env.CEREBROS_API_BASE;
delete process.env.NEXT_PUBLIC_CEREBROS_API_BASE;
