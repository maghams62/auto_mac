import type React from "react";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      webview: React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string;
        allow?: string;
        allowFullScreen?: boolean;
        allowTransparency?: boolean;
        allowpopups?: string | boolean;
        partition?: string;
        useragent?: string;
        disablewebsecurity?: string;
        nodeintegration?: string;
      };
    }
  }
}

export {};

