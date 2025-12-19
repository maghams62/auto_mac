import BrainTraceView from "@/components/BrainTraceView";

type Props = {
  params: {
    queryId: string;
  };
};

export const metadata = {
  title: "Brain Trace",
};

export default function BrainTracePage({ params }: Props) {
  return <BrainTraceView queryId={params.queryId} />;
}

