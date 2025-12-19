import type { ComponentType, ReactNode } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { isValidUrl } from "@/lib/utils/url-validation";

interface LinkChipProps {
  label: string;
  href?: string | null;
  icon?: ComponentType<{ className?: string }>;
  variant?: ButtonProps["variant"];
  size?: ButtonProps["size"];
  className?: string;
  children?: ReactNode;
}

export function LinkChip({
  label,
  href,
  icon: Icon,
  variant = "outline",
  size = "sm",
  className,
  children,
}: LinkChipProps) {
  if (!href || !isValidUrl(href)) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("[LinkChip] Ignoring invalid link", label, href);
    }
    return null;
  }

  return (
    <Button asChild variant={variant} size={size} className={cn("rounded-full", className)}>
      <a href={href} target="_blank" rel="noreferrer">
        {Icon ? <Icon className={cn(size === "sm" ? "mr-1.5 h-3.5 w-3.5" : "mr-2 h-4 w-4")} /> : null}
        {children ?? label}
      </a>
    </Button>
  );
}


