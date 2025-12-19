import IncidentDetailClient from "./IncidentDetailClient";

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ incidentId: string }>;
}) {
  const { incidentId } = await params;
  return <IncidentDetailClient incidentId={incidentId} />;
}


