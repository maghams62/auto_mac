"use client";

import ChatInterface from "@/components/ChatInterface";
import Header from "@/components/Header";

export default function Home() {
  return (
    <main className="relative min-h-screen flex flex-col">
      <Header />
      <div className="flex-1 flex flex-col">
        <ChatInterface />
      </div>
    </main>
  );
}
