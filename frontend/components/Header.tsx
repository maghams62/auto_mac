"use client";

export default function Header() {
  return (
    <header className="sticky top-0 z-50 bg-bg border-b border-surface-outline backdrop-blur-sm bg-opacity-80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-center h-14">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-accent-primary rounded-lg flex items-center justify-center">
              <span className="text-white font-semibold text-sm">C</span>
            </div>
            <h1 className="text-base font-semibold text-text-primary">
              Cerebro
            </h1>
          </div>
        </div>
      </div>
    </header>
  );
}
