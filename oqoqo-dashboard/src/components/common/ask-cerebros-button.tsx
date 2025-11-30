"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

interface AskCerebrosButtonProps {
  command: string;
  label?: string;
  size?: "default" | "sm" | "lg";
}

export function AskCerebrosButton({ command, label = "Copy Cerebros prompt", size = "sm" }: AskCerebrosButtonProps) {
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
    <Button variant="outline" size={size} className="rounded-full" onClick={handleCopy}>
      {copied ? "Copied" : label}
    </Button>
  );
}


