import { render, screen } from "@testing-library/react";
import IncidentReportTable from "../[incidentId]/IncidentReportTable";
import type { IncidentRecord } from "@/lib/types";

const baseIncident: IncidentRecord = {
  id: "incident-1",
  summary: "Test incident",
  severity: "low",
  status: "open",
  createdAt: "2025-01-01T00:00:00.000Z",
  incidentEntities: [
    {
      id: "doc-1",
      name: "Payments API",
      entityType: "doc",
      docStatus: { reason: "Needs vat_code appendix", severity: "high" },
      suggestedAction: "Update payments_api.md",
      evidenceIds: ["doc-evidence"],
      activitySignals: { doc_priority: 1 },
    },
  ],
  evidence: [
    {
      evidenceId: "doc-evidence",
      title: "Payments API doc",
      url: "https://example.com/payments_api",
    },
  ],
};

describe("IncidentReportTable", () => {
  it("renders rows for incident entities", () => {
    render(<IncidentReportTable incident={baseIncident} />);
    expect(screen.getByText("Payments API")).toBeInTheDocument();
    expect(screen.getByText("Needs vat_code appendix")).toBeInTheDocument();
    expect(screen.getByText("Update payments_api.md")).toBeInTheDocument();
    expect(screen.getByText("Payments API doc")).toHaveAttribute("href", "https://example.com/payments_api");
  });

  it("renders placeholder when no entities exist", () => {
    const incidentWithoutEntities: IncidentRecord = {
      ...baseIncident,
      id: "incident-empty",
      incidentEntities: undefined,
    };
    render(<IncidentReportTable incident={incidentWithoutEntities} />);
    expect(
      screen.getByText(
        /Impacted components, docs, and tickets will appear here once structured data is available./i,
      ),
    ).toBeInTheDocument();
  });
});
