"use client";

import { useEffect, useLayoutEffect } from "react";

import { logClientEvent } from "@/lib/logging";

declare global {
  interface Window {
    __OQOQO_HYDRATION_LOGGED__?: boolean;
    __OQOQO_HYDRATION_SCRUB_OBSERVER__?: MutationObserver | null;
  }
}

const ATTR_SELECTORS = ["[bis_skin_checked]", "[bis_register]"];
const ATTRIBUTE_PREFIXES = ["__processed"];

function stripSuspiciousAttributes() {
  if (typeof document === "undefined") return { removed: 0 };
  let removed = 0;
  const doc = document;
  const nodes = doc.querySelectorAll(ATTR_SELECTORS.join(","));
  nodes.forEach((node) => {
    ATTR_SELECTORS.forEach((selector) => {
      const attr = selector.replace(/[[\]]/g, "");
      if (node.getAttribute(attr) !== null) {
        node.removeAttribute(attr);
        removed += 1;
      }
    });
  });

  [doc.body, doc.documentElement].forEach((element) => {
    if (!element) return;
    Array.from(element.attributes).forEach((attr) => {
      if (
        attr.name === "bis_skin_checked" ||
        attr.name === "bis_register" ||
        ATTRIBUTE_PREFIXES.some((prefix) => attr.name.startsWith(prefix))
      ) {
        element.removeAttribute(attr.name);
        removed += 1;
      }
    });
  });

  return { removed };
}

function collectSuspiciousAttributes() {
  if (typeof document === "undefined") return [] as string[];
  const suspiciousAttributes: string[] = [];
  const collect = (element: HTMLElement | null) => {
    if (!element) return;
    Array.from(element.attributes).forEach((attr) => {
      if (
        attr.name.startsWith("bis_") ||
        attr.name === "bis_register" ||
        ATTRIBUTE_PREFIXES.some((prefix) => attr.name.startsWith(prefix))
      ) {
        suspiciousAttributes.push(attr.name);
      }
    });
  };
  collect(document.body);
  collect(document.documentElement);
  return suspiciousAttributes;
}

export function HydrationDiagnostics() {
  useLayoutEffect(() => {
    if (typeof window === "undefined") return;
    const disconnectObserver = () => {
      window.__OQOQO_HYDRATION_SCRUB_OBSERVER__?.disconnect();
      window.__OQOQO_HYDRATION_SCRUB_OBSERVER__ = null;
    };

    stripSuspiciousAttributes();
    if ("MutationObserver" in window && !window.__OQOQO_HYDRATION_SCRUB_OBSERVER__) {
      const observer = new MutationObserver(() => {
        stripSuspiciousAttributes();
      });
      observer.observe(document.documentElement, { attributes: true, childList: true, subtree: true });
      window.__OQOQO_HYDRATION_SCRUB_OBSERVER__ = observer;
      setTimeout(disconnectObserver, 2000);
    }

    return disconnectObserver;
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.__OQOQO_HYDRATION_LOGGED__) return;
    window.__OQOQO_HYDRATION_LOGGED__ = true;

    const suspiciousAttributes = collectSuspiciousAttributes();
    const payload = {
      userAgent: navigator.userAgent,
      suspiciousAttributes,
      loggedAt: new Date().toISOString(),
    };

    const eventName = suspiciousAttributes.length ? "hydration.extension-attrs" : "hydration.clean";
    logClientEvent(eventName, payload);
  }, []);

  return null;
}


