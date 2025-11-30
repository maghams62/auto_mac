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
            __html: `(function(){function scrub(){try{var nodes=document.querySelectorAll('[bis_skin_checked],[bis_register]');nodes.forEach(function(node){node.removeAttribute('bis_skin_checked');node.removeAttribute('bis_register');});var body=document.body;if(body){Array.from(body.attributes).forEach(function(attr){if(attr.name.indexOf('__processed')===0){body.removeAttribute(attr.name);}});}}catch(e){}}if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',scrub,{once:true});}else{scrub();}})();`,
          }}
        />
        <div className="noise-overlay" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
