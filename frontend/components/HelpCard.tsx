"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { scaleIn } from "@/lib/motion";

interface HelpCardProps {
  title: string;
  description?: string;
  examples?: string[];
  related?: string[];
  icon?: string;
  className?: string;
}

export default function HelpCard({
  title,
  description,
  examples,
  related,
  icon,
  className,
}: HelpCardProps) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={scaleIn}
      className={cn(
        "rounded-lg border border-glass bg-glass-assistant backdrop-blur-glass",
        "p-4 shadow-inset-border",
        className
      )}
    >
      <div className="flex items-start gap-3">
        {icon && <span className="text-xl flex-shrink-0">{icon}</span>}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-text-primary mb-1">{title}</h3>
          {description && (
            <p className="text-xs text-text-muted mb-2 leading-relaxed">{description}</p>
          )}
          {examples && examples.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-xs font-medium text-text-subtle uppercase tracking-wider">Examples:</p>
              {examples.map((example, idx) => (
                <code
                  key={idx}
                  className="block text-xs font-mono bg-glass rounded px-2 py-1 text-text-primary"
                >
                  {example}
                </code>
              ))}
            </div>
          )}
          {related && related.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium text-text-subtle uppercase tracking-wider mb-1">Related:</p>
              <div className="flex flex-wrap gap-1">
                {related.map((cmd, idx) => (
                  <span
                    key={idx}
                    className="text-xs font-mono px-2 py-0.5 bg-glass rounded text-accent-primary"
                  >
                    {cmd}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

