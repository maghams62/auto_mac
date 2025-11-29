import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import "../globals.css";
import { ToastProvider } from "@/lib/useToast";
import ToastStack from "@/components/ToastStack";

const inter = Inter({ subsets: ["latin"] });
const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono",
});

export const metadata: Metadata = {
  title: "Cerebros Launcher",
  description: "Raycast-style AI launcher for macOS",
};

export default function LauncherLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Minimal layout for launcher - no boot screen, no chat interface
  return (
    <html lang="en">
      <body className={`${inter.className} ${ibmPlexMono.variable}`}>
        <ToastProvider>
          {children}
          <ToastStack />
        </ToastProvider>
      </body>
    </html>
  );
}

