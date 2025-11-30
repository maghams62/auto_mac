"use client";

import { useEffect } from "react";

import { logClientEvent } from "@/lib/logging";

declare global {
  interface Window {
    __OQOQO_HYDRATION_LOGGED__?: boolean;
  }
}

export function HydrationDiagnostics() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.__OQOQO_HYDRATION_LOGGED__) return;
    window.__OQOQO_HYDRATION_LOGGED__ = true;

    const suspiciousAttributes: string[] = [];
    const collectAttributes = (element: HTMLElement | null) => {
      if (!element) return;
      Array.from(element.attributes).forEach((attr) => {
        if (
          attr.name.startsWith("bis_") ||
          attr.name.startsWith("__processed") ||
          attr.name === "bis_register"
        ) {
          suspiciousAttributes.push(attr.name);
        }
      });
    };

    collectAttributes(document.body);
    collectAttributes(document.documentElement);

    const payload = {
      userAgent: navigator.userAgent,
      suspiciousAttributes,
      loggedAt: new Date().toISOString(),
    };

    if (suspiciousAttributes.length) {
      logClientEvent("hydration.extension-attrs", payload);
    } else {
      logClientEvent("hydration.clean", payload);
    }
  }, []);

  return null;
}


