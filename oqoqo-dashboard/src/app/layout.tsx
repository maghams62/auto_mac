import type { Metadata } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Oqoqo Drift Dashboard",
  description:
    "DocDrift-inspired cockpit for configuring monitored repos, tracking activity graph signals, and resolving cross-system documentation drift.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} bg-background text-foreground`}>
        <Script
          id="strip-extension-attrs"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(function(){var SCRUB_DURATION=2000;function scrubAttributes(){try{var doc=document;var targets=[doc.body,doc.documentElement];var nodes=doc.querySelectorAll('[bis_skin_checked],[bis_register]');nodes.forEach(function(node){node.removeAttribute('bis_skin_checked');node.removeAttribute('bis_register');});targets.forEach(function(el){if(!el)return;Array.from(el.attributes).forEach(function(attr){if(attr.name==='bis_skin_checked'||attr.name==='bis_register'||attr.name.indexOf('__processed')===0){el.removeAttribute(attr.name);}});});}catch(e){}}function startObserver(){if(!('MutationObserver'in window))return;var observer=new MutationObserver(function(){scrubAttributes();});observer.observe(document.documentElement,{attributes:true,subtree:true,childList:true});setTimeout(function(){observer.disconnect();},SCRUB_DURATION);}function init(){scrubAttributes();startObserver();}if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init,{once:true});}else{init();}})();`,
          }}
        />
        <div className="noise-overlay" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
