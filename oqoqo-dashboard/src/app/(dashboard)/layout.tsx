import AppShell from "@/components/layout/app-shell";
import { redirect } from "next/navigation";

type LayoutProps = {
  children: React.ReactNode;
  params?: { segments?: string[] };
};

const INTERNAL_SEGMENTS = ["projects", "settings"];

export default function DashboardLayout({ children, params }: LayoutProps) {
  const firstSegment = params?.segments?.[0];
  if (firstSegment && !INTERNAL_SEGMENTS.includes(firstSegment)) {
    redirect(`/${firstSegment}`);
  }
  return <AppShell>{children}</AppShell>;
}

