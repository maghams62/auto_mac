import type { Metadata } from "next";
import { Inter, Courier_Prime, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { ToastProvider } from "@/lib/useToast";
import ToastStack from "@/components/ToastStack";
import ClientLayout from "./ClientLayout";

const inter = Inter({ subsets: ["latin"] });
const courierPrime = Courier_Prime({ 
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-courier-prime",
});
const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono",
});

export const metadata: Metadata = {
  title: "Cerebro OS",
  description: "Your AI assistant for Mac automation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} ${courierPrime.variable} ${ibmPlexMono.variable}`}>
        <ToastProvider>
          <ClientLayout>{children}</ClientLayout>
          <ToastStack />
        </ToastProvider>
      </body>
    </html>
  );
}
