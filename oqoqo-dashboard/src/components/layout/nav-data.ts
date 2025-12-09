import type { ComponentType } from "react";
import { LayoutDashboard, Network, Settings2 } from "lucide-react";

import { ENABLE_PROTOTYPE_ADMIN } from "@/lib/feature-flags";

export type WorkspaceNavItem = {
  label: string;
  description: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
};

const DEFAULT_BRAIN_HREF = "/brain/universe";
const brainUniverseHref =
  process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL?.trim() || DEFAULT_BRAIN_HREF;

const baseItems: WorkspaceNavItem[] = [
  {
    label: "All projects",
    description: "Scan doc health and pick a project to dive into.",
    href: "/projects",
    icon: LayoutDashboard,
  },
  {
    label: "Brain",
    description: "Fly the 3D universe and inspect reasoning traces.",
    href: brainUniverseHref,
    icon: Network,
  },
];

if (ENABLE_PROTOTYPE_ADMIN) {
  baseItems.push({
    label: "System settings",
    description: "Control source-of-truth, git monitoring, and automation.",
    href: "/settings",
    icon: Settings2,
  });
}

export const workspaceNavItems: WorkspaceNavItem[] = baseItems;

