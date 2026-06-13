"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const tabs = [
  { href: "/review", label: "AI Reviewer" },
  { href: "/personalize", label: "Target an Audience" }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-paper">
      <LiveBackdrop />
      <div className="relative z-10 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="shell-frame flex flex-col gap-8">
          <header className="rounded-lg border border-line bg-white/95 px-6 py-5 shadow-board md:flex md:items-center md:justify-between">
            <div>
              <div className="text-xs font-bold uppercase tracking-widest text-muted">Stars of Science</div>
              <h1 className="mt-1 text-3xl font-black text-ink sm:text-4xl">Masar</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                Platform intelligence and audience delivery planning built specifically for Stars of Science.
              </p>
            </div>
            <nav className="mt-4 flex rounded-lg border border-line bg-paper/80 p-1 md:mt-0">
              {tabs.map((tab) => {
                const active = pathname === tab.href || (pathname === "/" && tab.href === "/review");
                return (
                  <Link
                    key={tab.href}
                    href={tab.href}
                    className={`rounded px-5 py-2 text-sm font-bold transition ${
                      active
                        ? "bg-accent text-white shadow-sm"
                        : "text-muted hover:text-ink"
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
      </div>
    </main>
  );
}

function LiveBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <span className="live-halo live-halo-a" />
      <span className="live-halo live-halo-b" />
      <span className="live-panel live-panel-a" />
      <span className="live-panel live-panel-b" />
      <span className="live-grid live-grid-a" />
      <span className="live-grid live-grid-b" />
      <span className="live-line live-line-a" />
      <span className="live-line live-line-b" />
      <span className="live-square live-square-a" />
      <span className="live-square live-square-b" />
    </div>
  );
}
