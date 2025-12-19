"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { buildCerebrosUrl, buildInvestigationUrl } from "@/lib/cerebros";
import { isValidUrl } from "@/lib/utils/url-validation";

type RunStatus = "idle" | "loading" | "success" | "error";

type GraphAskResponse = {
  error?: string;
  message?: string;
  investigation_id?: string;
  investigationId?: string;
  id?: string;
  url?: string;
  result?: {
    investigation_id?: string;
  };
};

interface AskCerebrosRunButtonProps {
  projectId: string;
  projectSlug?: string;
  componentId?: string;
  issueId?: string;
  query: string;
  label?: string;
  size?: ButtonProps["size"];
  variant?: ButtonProps["variant"];
  containerClassName?: string;
  buttonClassName?: string;
}

const resolveCerebrosHref = (value?: string) => {
  if (!value) return undefined;
  if (isValidUrl(value)) {
    return value;
  }
  if (value.startsWith("/")) {
    return buildCerebrosUrl(value);
  }
  return undefined;
};

export function AskCerebrosButton({
  projectId,
  projectSlug,
  componentId,
  issueId,
  query,
  label = "Ask Cerebros",
  size = "sm",
  variant = "outline",
  containerClassName,
  buttonClassName,
}: AskCerebrosRunButtonProps) {
  const [status, setStatus] = useState<RunStatus>("idle");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [investigationUrl, setInvestigationUrl] = useState<string | null>(null);

  const isLoading = status === "loading";
  const isDisabled = isLoading || !query.trim();

  const handleAsk = async () => {
    if (isDisabled) return;
    setStatus("loading");
    setStatusMessage(null);
    setInvestigationUrl(null);

    const graphParams: Record<string, unknown> = { projectId };
    if (projectSlug) graphParams.projectSlug = projectSlug;
    if (componentId) graphParams.componentId = componentId;
    if (issueId) graphParams.issueId = issueId;

    try {
      const response = await fetch("/api/cerebros/ask-graph", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, graphParams }),
      });
      let parsed: GraphAskResponse | null = null;
      try {
        parsed = (await response.json()) as GraphAskResponse;
      } catch {
        parsed = null;
      }
      if (!response.ok) {
        setStatus("error");
        setStatusMessage(parsed?.error ?? "Cerebros request failed.");
        return;
      }
      const runId =
        parsed?.investigation_id ??
        parsed?.investigationId ??
        parsed?.id ??
        parsed?.result?.investigation_id ??
        null;
      const runUrl =
        resolveCerebrosHref(parsed?.url) ??
        (runId ? buildInvestigationUrl(runId) : undefined);
      setStatus("success");
      setStatusMessage(parsed?.message ?? "Ask sent to Cerebros.");
      setInvestigationUrl(runUrl ?? null);
    } catch (error) {
      setStatus("error");
      setStatusMessage(error instanceof Error ? error.message : "Cerebros request failed.");
    }
  };

  const buttonLabel = isLoading ? (
    <span className="inline-flex items-center gap-2">
      <Loader2 className="h-4 w-4 animate-spin" />
      Asking…
    </span>
  ) : (
    label
  );

  return (
    <div className={cn("inline-flex min-w-0 flex-col gap-1", containerClassName)}>
      <Button
        variant={variant}
        size={size}
        className={cn("rounded-full", buttonClassName)}
        disabled={isDisabled}
        onClick={handleAsk}
      >
        {buttonLabel}
      </Button>
      {status === "error" && statusMessage ? (
        <p className="text-xs text-destructive">{statusMessage}</p>
      ) : null}
      {status === "success" ? (
        <p className="text-xs text-muted-foreground">
          {statusMessage ?? "Ask sent to Cerebros."}{" "}
          {investigationUrl ? (
            <a href={investigationUrl} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">
              View in Cerebros
            </a>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

interface AskCerebrosCopyButtonProps {
  command: string;
  label?: string;
  size?: ButtonProps["size"];
  variant?: ButtonProps["variant"];
  className?: string;
}

export function AskCerebrosCopyButton({
  command,
  label = "Copy Cerebros prompt",
  size = "sm",
  variant = "outline",
  className,
}: AskCerebrosCopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.warn("Failed to copy Cerebros command", error);
    }
  };

  return (
    <Button variant={variant} size={size} className={cn("rounded-full", className)} onClick={handleCopy}>
      {copied ? "Copied" : label}
    </Button>
  );
}
