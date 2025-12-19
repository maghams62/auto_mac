import type { ComponentType } from "react";
import { BookOpen, GitBranch, MessageSquare, Sparkles } from "lucide-react";

import { LinkChip } from "@/components/common/link-chip";
import { cn } from "@/lib/utils";
import { isValidUrl } from "@/lib/utils/url-validation";

type DeepLinkButtonsProps = {
  githubUrl?: string;
  slackUrl?: string;
  docUrl?: string;
  cerebrosUrl?: string;
  size?: "sm" | "md";
  className?: string;
};

const sizeClasses: Record<NonNullable<DeepLinkButtonsProps["size"]>, string> = {
  sm: "rounded-full px-3 text-xs",
  md: "rounded-full px-4 text-sm",
};

const dashboardOrigin =
  process.env.NEXT_PUBLIC_SITE_URL ??
  process.env.NEXT_PUBLIC_DASHBOARD_URL ??
  process.env.NEXT_PUBLIC_APP_URL ??
  "";

const normalizeOrigin = (value?: string | null) => {
  if (!value) return "";
  return value.endsWith("/") ? value.replace(/\/+$/, "") : value;
};

const resolveHref = (value?: string) => {
  if (!value) return null;
  if (isValidUrl(value)) {
    return value;
  }
  if (value.startsWith("/")) {
    const origin =
      normalizeOrigin(dashboardOrigin) ||
      (typeof window !== "undefined" ? window.location.origin : "");
    if (!origin) {
      return null;
    }
    return `${origin}${value}`;
  }
  return null;
};

export function DeepLinkButtons({
  githubUrl,
  slackUrl,
  docUrl,
  cerebrosUrl,
  size = "sm",
  className,
}: DeepLinkButtonsProps) {
  const resolvedGithub = resolveHref(githubUrl);
  const resolvedSlack = resolveHref(slackUrl);
  const resolvedDoc = resolveHref(docUrl);
  const resolvedCerebros = resolveHref(cerebrosUrl);

  const links = [
    resolvedGithub ? { href: resolvedGithub, label: "View PR", Icon: GitBranch } : null,
    resolvedSlack ? { href: resolvedSlack, label: "View Slack thread", Icon: MessageSquare } : null,
    resolvedDoc ? { href: resolvedDoc, label: "View doc", Icon: BookOpen } : null,
    resolvedCerebros ? { href: resolvedCerebros, label: "Open in Cerebros", Icon: Sparkles } : null,
  ].filter(Boolean) as Array<{ href: string; label: string; Icon: ComponentType<{ className?: string }> }>;

  if (!links.length) {
    return null;
  }

  const buttonClass = sizeClasses[size];
  const iconClass = size === "md" ? "mr-1.5 h-4 w-4" : "mr-1.5 h-3.5 w-3.5";

  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {links.map((link) => (
        <LinkChip
          key={link.label}
          label={link.label}
          href={link.href}
          icon={link.Icon}
          variant="outline"
          size={size === "md" ? "default" : "sm"}
          className={buttonClass}
        />
      ))}
    </div>
  );
}

