import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ToastProvider } from "@/lib/useToast";
import ToastStack from "@/components/ToastStack";

const inter = Inter({ subsets: ["latin"] });

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
      <body className={inter.className}>
        <ToastProvider>
          {children}
          <ToastStack />
        </ToastProvider>
      </body>
    </html>
  );
}
