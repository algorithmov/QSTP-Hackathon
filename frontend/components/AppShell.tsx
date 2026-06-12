"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const tabs = [
  { href: "/review", label: "AI Reviewer" },
  { href: "/personalize", label: "Personalized Targeter" }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-paper">
      <LiveBackdrop />
      <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="rounded-md border border-line bg-white/95 px-5 py-4 shadow-board md:flex md:items-end md:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-wide text-accent">Stars of Science</div>
            <h1 className="mt-1 text-3xl font-black tracking-normal text-ink sm:text-4xl">Masar</h1>
            <p className="mt-2 max-w-2xl text-base leading-7 text-muted">
              Evidence-backed routing and localized delivery plans for Stars of Science ideas.
            </p>
          </div>
          <nav className="mt-4 flex w-full rounded-md border border-line bg-paper p-1 md:mt-0 md:w-auto">
            {tabs.map((tab) => {
              const active = pathname === tab.href || (pathname === "/" && tab.href === "/review");
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex-1 rounded px-4 py-2 text-center text-sm font-bold transition md:flex-none ${
                    active ? "bg-accent text-white" : "text-ink hover:bg-paper"
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </header>
        {children}
      </div>
    </main>
  );
}

function LiveBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <span className="live-grid live-grid-a" />
      <span className="live-grid live-grid-b" />
      <span className="live-line live-line-a" />
      <span className="live-line live-line-b" />
      <span className="live-square live-square-a" />
      <span className="live-square live-square-b" />
    </div>
  );
}
